import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select, update

from app.core.errors import ApiError
from app.product.db import now
from app.product.tables import Membership, Subscription, UsageEvent, Workspace


@dataclass(frozen=True)
class Plan:
    name: str
    documents_per_month: int
    max_file_bytes: int
    seats: int
    history_days: int
    api_access: bool
    reader_branding: bool
    price: int | None

    def public_limits(self) -> dict:
        limits = asdict(self)
        del limits["price"]
        return limits


PLAN_PRICES = json.loads(Path(__file__).with_name("plan_prices.json").read_text(encoding="utf-8"))
PLANS = {
    "free": Plan("Free", 5, 5_000_000, 2, 7, False, False, PLAN_PRICES["free"]),
    "educator": Plan("Educator", 50, 10_000_000, 5, 30, False, False, PLAN_PRICES["educator"]),
    "institution": Plan("Institution", 500, 10_000_000, 50, 30, True, True, PLAN_PRICES["institution"]),
}


def workspace_plan(db, workspace_id) -> Plan:
    subscription = db.get(Subscription, workspace_id)
    return PLANS[subscription.plan if subscription else "free"]


def lock_workspace(db, workspace_id):
    # Acquire a write lock in SQLite and a row lock in Postgres before counting quota.
    db.execute(update(Workspace).where(Workspace.id == workspace_id).values(name=Workspace.name))


def usage(db, workspace_id, kind):
    month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count()).select_from(UsageEvent).where(
        UsageEvent.workspace_id == workspace_id, UsageEvent.kind == kind, UsageEvent.created_at >= month,
    ))


def check_upload(db, workspace_id, size):
    lock_workspace(db, workspace_id)
    check_upload_quota(db, workspace_id, size)


def check_upload_quota(db, workspace_id, size):
    plan = workspace_plan(db, workspace_id)
    count = usage(db, workspace_id, "audit")
    if count >= plan.documents_per_month:
        raise ApiError(429, "plan_limit", f"You’ve used {count} of {plan.documents_per_month} documents this month. See Pricing for more capacity.")
    if size > plan.max_file_bytes:
        raise ApiError(413, "file_too_large", f"Your plan allows Word files up to {plan.max_file_bytes // 1_000_000} MB.")


def check_seat(db, workspace_id):
    lock_workspace(db, workspace_id)
    count = db.scalar(select(func.count()).select_from(Membership).where(Membership.workspace_id == workspace_id))
    if count >= workspace_plan(db, workspace_id).seats:
        raise ApiError(409, "plan_seats", "This workspace has used all its seats. See Pricing for more capacity.")
