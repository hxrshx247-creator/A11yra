from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.audit.runner import run_audit
from app.core.errors import ApiError
from app.core.validation import read_docx
from app.models import Audit
from app.product.db import now
from app.product.http import audit_timeout_error
from app.product.plans import check_upload, check_upload_quota, lock_workspace, workspace_plan
from app.product.security import TOKEN_PATTERN, digest, get_db, log_event, token
from app.product.tables import ApiKey, UsageEvent
from app.product.workspaces import require_role

router = APIRouter(prefix="/api", tags=["Integration API"])
bearer = HTTPBearer(auto_error=False)


class KeyInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/workspaces/{workspace_id}/keys")
def list_keys(context=Depends(require_role("owner")), db=Depends(get_db)):
    _, workspace, _ = context
    return [{"id": key.id, "name": key.name, "created_at": key.created_at,
             "last_used_at": key.last_used_at, "revoked_at": key.revoked_at}
            for key in db.scalars(select(ApiKey).where(ApiKey.workspace_id == workspace)
                                  .order_by(ApiKey.created_at.desc()).limit(100))]


@router.post("/workspaces/{workspace_id}/keys", status_code=201)
def create_key(body: KeyInput, request: Request, context=Depends(require_role("owner")), db=Depends(get_db)):
    user, workspace, _ = context
    if not workspace_plan(db, workspace).api_access:
        raise ApiError(403, "plan_api", "API access is available on the Institution plan.")
    request.app.state.auth_limits.hit(("api_keys", user.id), 10, 3600)
    raw = token()
    key = ApiKey(workspace_id=workspace, name=body.name, digest=digest(raw))
    db.add(key)
    db.flush()
    log_event(db, "api_key_created", "api_key", request=request, workspace=workspace, actor=user.id, target=key.id)
    db.commit()
    return {"id": key.id, "key": f"a11yra_{raw}"}


@router.delete("/workspaces/{workspace_id}/keys/{key_id}", status_code=204)
def revoke_key(key_id: UUID, request: Request, context=Depends(require_role("owner")), db=Depends(get_db)):
    user, workspace, _ = context
    lock_workspace(db, workspace)
    key = db.get(ApiKey, str(key_id))
    if not key or key.workspace_id != workspace:
        raise ApiError(404, "key_not_found", "This API key could not be found.")
    if not key.revoked_at:
        key.revoked_at = now()
        log_event(db, "api_key_revoked", "api_key", request=request, workspace=workspace, actor=user.id, target=key.id)
        db.commit()


def authorized_key(request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    if auth and auth.credentials.startswith("a11yra_") and TOKEN_PATTERN.fullmatch(auth.credentials[7:]):
        key = db.scalar(select(ApiKey).where(ApiKey.digest == digest(auth.credentials[7:]), ApiKey.revoked_at.is_(None)))
        if key and workspace_plan(db, key.workspace_id).api_access:
            request.app.state.user_limits.hit(("api_key", key.id), 20, 60)
            return key.id, key.workspace_id
    raise ApiError(401, "invalid_api_key", "Supply an active API key for a workspace with API access.")


@router.post("/public/v1/audit", response_model=Audit)
def public_audit(request: Request, file: Annotated[UploadFile, File()], key=Depends(authorized_key)):
    slots = request.app.state.public_audit_slots
    if not slots.acquire(blocking=False):
        raise ApiError(429, "rate_limit", "Too many requests. Wait a little and try again.")
    try:
        return execute_public_audit(request, file, key)
    finally:
        slots.release()


def check_audit_deadline(request: Request) -> None:
    if perf_counter() >= request.state.public_audit_deadline:
        raise audit_timeout_error()


def execute_public_audit(request, file, credentials) -> Audit:
    key_id, workspace_id = credentials
    sessions = request.app.state.sessions
    check_audit_deadline(request)
    _, contents, document = read_docx(file)
    check_audit_deadline(request)
    with sessions() as db:
        check_upload_quota(db, workspace_id, len(contents))
    check_audit_deadline(request)
    audit = run_audit(document, uuid4())
    check_audit_deadline(request)
    with sessions() as db:
        check_upload(db, workspace_id, len(contents))
        key = db.get(ApiKey, key_id)
        if key is None or key.revoked_at or not workspace_plan(db, workspace_id).api_access:
            raise ApiError(401, "invalid_api_key", "Supply an active API key for a workspace with API access.")
        check_audit_deadline(request)
        key.last_used_at = now()
        db.add(UsageEvent(workspace_id=workspace_id, kind="audit"))
        log_event(db, "audit_run", "api_key", request=request, workspace=workspace_id, target=key.id)
        db.commit()
    return audit
