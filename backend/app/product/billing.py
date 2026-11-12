import os
from time import time
from typing import Literal

import stripe
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.errors import ApiError
from app.product.plans import PLANS, lock_workspace
from app.product.security import get_db, log_event
from app.product.tables import Subscription
from app.product.workspaces import require_role

router = APIRouter(prefix="/api", tags=["Plans and test billing"])


class Billing:
    def __init__(self, environment):
        key = os.getenv("STRIPE_SECRET_KEY", "")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.prices = {plan: os.getenv(f"STRIPE_PRICE_{plan.upper()}", "") for plan in ("educator", "institution")}
        self.enabled = (os.getenv("STRIPE_TEST_ENABLED") == "1" and key.startswith("sk_test_")
                        and self.webhook_secret.startswith("whsec_")
                        and all(price.startswith("price_") for price in self.prices.values()))
        self.client = stripe.StripeClient(key, max_network_retries=1) if self.enabled else None
        self.demo_changes = environment == "dev" or os.getenv("A11YRA_DEMO_PLAN_CHANGES") == "1"


class PlanInput(BaseModel):
    plan: Literal["free", "educator", "institution"]


@router.get("/plans")
def plans(request: Request):
    billing = request.app.state.billing
    return {"plans": {name: plan.public_limits() for name, plan in PLANS.items()},
            "billing_demo": not billing.enabled, "demo_changes": billing.demo_changes}


def change_plan(db, subscription, plan, *, request=None, actor=None):
    if subscription.plan != plan:
        subscription.plan = plan
        log_event(db, "plan_changed", "workspace", request=request, workspace=subscription.workspace_id,
                  actor=actor, target=subscription.workspace_id, metadata={"plan": plan})


@router.post("/workspaces/{workspace_id}/billing/demo", status_code=204)
def demo(body: PlanInput, request: Request, context=Depends(require_role("owner")), db=Depends(get_db)):
    user, workspace, _ = context
    billing = request.app.state.billing
    if billing.enabled or not billing.demo_changes:
        raise ApiError(403, "demo_unavailable", "Demo plan changes are disabled.")
    lock_workspace(db, workspace)
    change_plan(db, db.get(Subscription, workspace), body.plan, request=request, actor=user.id)
    db.commit()


@router.post("/workspaces/{workspace_id}/billing/checkout")
def checkout(body: PlanInput, request: Request, context=Depends(require_role("owner")), db=Depends(get_db)):
    user, workspace, _ = context
    billing = request.app.state.billing
    if not billing.enabled:
        raise ApiError(409, "billing_demo", "Billing is in demo mode.")
    if body.plan == "free" or db.get(Subscription, workspace).stripe_subscription:
        raise ApiError(409, "checkout_unavailable", "Manage an existing test subscription in Stripe.")
    if not user.email_verified:
        raise ApiError(403, "email_verification", "Verify your email before starting test checkout.")
    request.app.state.auth_limits.hit(("checkout", user.id), 6, 3600)
    base = request.app.state.public_url
    try:
        session = billing.client.v1.checkout.sessions.create({
            "mode": "subscription", "customer_email": user.email, "payment_method_types": ["card"],
            "line_items": [{"price": billing.prices[body.plan], "quantity": 1}],
            "subscription_data": {"metadata": {"workspace_id": workspace}},
            "success_url": f"{base}/pricing?checkout=complete", "cancel_url": f"{base}/pricing",
        }, options={"idempotency_key": f"checkout-{workspace}-{body.plan}-{int(time()) // 1800}"})
    except stripe.StripeError:
        raise ApiError(502, "stripe_unavailable", "Stripe test checkout could not be opened. Try again.") from None
    return {"url": session.url}


@router.post("/billing/webhook", status_code=204)
async def webhook(request: Request, db=Depends(get_db)):
    from starlette.concurrency import run_in_threadpool

    billing = request.app.state.billing
    if not billing.enabled:
        raise ApiError(404, "billing_demo", "Billing is in demo mode.")
    try:
        event = stripe.Webhook.construct_event(
            await request.body(), request.headers.get("stripe-signature", ""), billing.webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise ApiError(400, "stripe_signature", "The webhook signature could not be verified.") from None
    if event.livemode or event.type not in {
        "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted",
    }:
        return
    await run_in_threadpool(apply_event, db, billing, event)


def apply_event(db, billing, event):
    from uuid import UUID

    snapshot = event.data.object
    try:
        workspace = str(UUID(snapshot.metadata["workspace_id"]))
    except (AttributeError, KeyError, ValueError, TypeError):
        return
    lock_workspace(db, workspace)
    subscription = db.get(Subscription, workspace)
    if (not subscription or event.created < subscription.stripe_event_at
            or subscription.stripe_subscription not in {None, snapshot.id}):
        return
    if event.type == "customer.subscription.deleted":
        plan = "free"
    else:
        try:
            current = billing.client.v1.subscriptions.retrieve(snapshot.id)
        except stripe.StripeError:
            raise ApiError(502, "stripe_unavailable", "Stripe could not confirm the test subscription.") from None
        if current.livemode:
            return
        price = current.items.data[0].price.id if current.items.data else None
        plan = next((name for name, value in billing.prices.items() if value == price), "free")
        if current.status not in {"active", "trialing"}:
            plan = "free"
    subscription.stripe_subscription = None if event.type == "customer.subscription.deleted" else snapshot.id
    subscription.stripe_event_at = event.created
    change_plan(db, subscription, plan)
    db.commit()
