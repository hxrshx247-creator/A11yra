from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.core.errors import ApiError
from app.product.auth import EmailInput, LinkToken, personal_workspace, send_mail
from app.product.db import now
from app.product.plans import check_seat, lock_workspace, usage, workspace_plan
from app.product.security import digest, get_db, log_event, signed_in, token
from app.product.tables import AuditLog, Document, Invite, Membership, User, Workspace

router = APIRouter(prefix="/api", tags=["Workspaces"])
ROLES = {"viewer": 0, "editor": 1, "owner": 2}


class InviteInput(EmailInput):
    role: Literal["editor", "viewer"]


class RoleInput(BaseModel):
    role: Literal["editor", "viewer"]


def document_not_found():
    return ApiError(404, "document_not_found", "This document could not be found.")


def require_role(role, *, document=False, active=False):
    def dependency(request: Request, db=Depends(get_db)):
        user = signed_in(request, db)
        item = None
        if document:
            try:
                item = db.get(Document, str(UUID(request.path_params["id"])))
            except ValueError:
                raise document_not_found() from None
            if not item or item.history_until <= now():
                raise document_not_found()
            workspace = item.workspace_id
        else:
            workspace = (request.path_params.get("workspace_id")
                         or request.headers.get("x-workspace-id")
                         or personal_workspace(db, user.id))
            try:
                workspace = str(UUID(workspace))
            except (ValueError, TypeError):
                raise ApiError(404, "workspace_not_found", "This workspace could not be found.") from None
        member = db.get(Membership, (workspace, user.id))
        if not member:
            if document:
                raise document_not_found()
            raise ApiError(404, "workspace_not_found", "This workspace could not be found.")
        if ROLES[member.role] < ROLES[role]:
            raise ApiError(403, "role_required", "Your workspace role does not allow this action.")
        if active and (item.status != "active" or item.expires_at <= now()):
            raise document_not_found()
        return user, workspace, item
    return dependency


@router.get("/workspaces/{workspace_id}/members")
def members(workspace_id: UUID, context=Depends(require_role("owner")), db=Depends(get_db)):
    return [{"id": user_id, "email": email, "role": role} for user_id, email, role in db.execute(
        select(Membership.user_id, User.email, Membership.role)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == str(workspace_id)).order_by(User.email)
    )]


@router.post("/workspaces/{workspace_id}/invites", status_code=202)
def invite(body: InviteInput, request: Request, tasks: BackgroundTasks,
           context=Depends(require_role("owner")), db=Depends(get_db)):
    user, workspace, _ = context
    request.app.state.auth_limits.hit(("invites", user.id), 20, 3600)
    if not user.email_verified:
        raise ApiError(403, "email_verification", "Verify your email before inviting colleagues.")
    check_seat(db, workspace)
    raw = token()
    db.execute(delete(Invite).where(Invite.workspace_id == workspace, Invite.email == body.email))
    invitation = Invite(workspace_id=workspace, invited_by=user.id, email=body.email, role=body.role,
                        digest=digest(raw), expires_at=now() + timedelta(days=7))
    db.add(invitation)
    db.flush()
    log_event(db, "invite_sent", "invitation", request=request, workspace=workspace, actor=user.id,
              target=invitation.id, metadata={"role": body.role})
    name = db.get(Workspace, workspace).name
    tasks.add_task(send_mail, request, body.email, "You were invited to an A11yra workspace",
                   f"{user.email} invited you to {name}.\n"
                   f"{request.app.state.public_url}/account/invite#token={raw}\nThe link expires in 7 days.")
    db.commit()
    return {"message": "Invitation queued."}


@router.post("/invites/accept")
def accept(body: LinkToken, request: Request, db=Depends(get_db)):
    user = signed_in(request, db)
    if not user.email_verified:
        raise ApiError(403, "email_verification", "Verify your email before accepting this invitation.")
    invitation = db.scalar(select(Invite).where(
        Invite.digest == digest(body.token), Invite.email == user.email, Invite.expires_at > now(),
    ))
    if not invitation:
        raise ApiError(404, "invite_not_found", "This invitation is unavailable for this account.")
    workspace = invitation.workspace_id
    lock_workspace(db, workspace)
    db.refresh(invitation)
    if db.get(Membership, (workspace, user.id)) is None:
        check_seat(db, workspace)
        db.add(Membership(workspace_id=workspace, user_id=user.id, role=invitation.role))
    log_event(db, "invite_accepted", "invitation", request=request, workspace=workspace, actor=user.id,
              target=invitation.id)
    db.delete(invitation)
    db.commit()
    return {"workspace_id": workspace}


@router.patch("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
def change_role(user_id: UUID, body: RoleInput, request: Request, context=Depends(require_role("owner")),
                db=Depends(get_db)):
    user, workspace, _ = context
    member = db.get(Membership, (workspace, str(user_id)))
    if not member or member.role == "owner":
        raise ApiError(404, "member_not_found", "This editable membership could not be found.")
    member.role = body.role
    log_event(db, "role_changed", "member", request=request, workspace=workspace, actor=user.id,
              target=str(user_id), metadata={"role": body.role})
    db.commit()


@router.get("/workspaces/{workspace_id}/usage")
def workspace_usage(request: Request, context=Depends(require_role("viewer")), db=Depends(get_db)):
    _, workspace, _ = context
    plan = workspace_plan(db, workspace)
    return {"plan": plan.public_limits(), "documents_used": usage(db, workspace, "audit"),
            "exports": usage(db, workspace, "export"), "file_hours": request.app.state.file_hours,
            "billing_demo": not request.app.state.billing.enabled}


@router.get("/workspaces/{workspace_id}/documents")
def documents(context=Depends(require_role("viewer")), db=Depends(get_db)):
    _, workspace, _ = context
    return [{"id": doc.id, "filename": doc.filename, "status": doc.status if doc.expires_at > now() else "expired",
             "expires_at": doc.expires_at, "created_at": doc.created_at} for doc in db.scalars(
        select(Document).where(Document.workspace_id == workspace, Document.history_until > now())
        .order_by(Document.created_at.desc()).limit(500)
    )]


def csv_response(filename, headers, rows):
    import csv
    from io import StringIO

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([
            "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
            for value in row
        ])
    return Response(output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/workspaces/{workspace_id}/activity")
def activity(actor: UUID | None = None, action: str | None = None, start: date | None = None,
             end: date | None = None, format: Literal["json", "csv"] = "json",
             context=Depends(require_role("editor")), db=Depends(get_db)):
    _, workspace, _ = context
    query = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_user_id).where(
        AuditLog.workspace_id == workspace,
    )
    if actor:
        query = query.where(AuditLog.actor_user_id == str(actor))
    if action:
        query = query.where(AuditLog.action == action)
    if start:
        query = query.where(AuditLog.created_at >= datetime.combine(start, time.min))
    if end:
        query = query.where(AuditLog.created_at <= datetime.combine(end, time.max))
    rows = [{"created_at": row.created_at.isoformat() + "Z", "actor": email, "actor_id": row.actor_user_id,
             "action": row.action, "target_type": row.target_type, "target_id": row.target_id}
            for row, email in db.execute(query.order_by(AuditLog.created_at.desc()).limit(1000))]
    if format == "csv":
        headers = ["created_at", "actor", "actor_id", "action", "target_type", "target_id"]
        return csv_response("a11yra-activity.csv", headers, ([row[key] for key in headers] for row in rows))
    return rows
