from datetime import timedelta
import re

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.errors import ApiError
from app.product.db import now
from app.product.security import (
    ACCESS, ACCESS_SECONDS, CSRF, REFRESH, REFRESH_SECONDS, clear_cookies, csrf_cookie,
    current_session, digest, get_db, log_event, set_cookie, signed_in, token, valid_csrf_cookie, validate_csrf,
)
from app.product.tables import (
    AccountToken, AuditLog, AuditRecord, Document, Invite, Membership, ReaderShare,
    Session, Subscription, User, Workspace,
)

router = APIRouter(prefix="/api/auth", tags=["Account"])
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(token())


class EmailInput(BaseModel):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
            raise ValueError("Enter an email address.")
        return value


class Credentials(EmailInput):
    password: str = Field(min_length=1, max_length=128)


class LinkToken(BaseModel):
    token: str = Field(min_length=43, max_length=43)


class PasswordReset(LinkToken):
    password: str = Field(min_length=12, max_length=128)


class ConfirmDeletion(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: bool


def personal_workspace(db, user_id):
    return db.scalar(select(Workspace.id).where(Workspace.personal_owner_id == user_id))


def profile(db, user):
    memberships = db.execute(
        select(Workspace, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Workspace.created_at)
    )
    return {
        "id": user.id, "email": user.email, "email_verified": user.email_verified,
        "workspaces": [
            {"id": workspace.id, "name": workspace.name, "role": role,
             "personal": workspace.personal_owner_id == user.id}
            for workspace, role in memberships
        ],
    }


def session_cookies(request, response, access, refresh, csrf, refresh_seconds=REFRESH_SECONDS):
    set_cookie(request, response, ACCESS, access, ACCESS_SECONDS)
    set_cookie(request, response, REFRESH, refresh, refresh_seconds)
    csrf_cookie(request, response, csrf)


def open_session(db, request, response, user):
    access, refresh, csrf = token(), token(), token()
    db.add(Session(
        user_id=user.id, access_hash=digest(access), refresh_hash=digest(refresh), csrf_hash=digest(csrf),
        access_until=now() + timedelta(seconds=ACCESS_SECONDS),
        expires_at=now() + timedelta(seconds=REFRESH_SECONDS),
    ))
    db.commit()
    session_cookies(request, response, access, refresh, csrf)


def verify_password(password, hashed):
    try:
        return hasher.verify(hashed, password)
    except VerificationError:
        return False


def send_mail(request, email, subject, content):
    try:
        request.app.state.mailer.send(email, subject, content)
    except (OSError, ValueError, KeyError):
        request.app.state.logger.warning('{"event":"mail_delivery_failed"}')


def schedule_link(db, request, tasks, user, purpose):
    if request.app.state.mailer.disabled:
        return
    raw = token()
    hours = 1 if purpose == "reset" else 24
    db.add(AccountToken(
        digest=digest(raw), user_id=user.id, purpose=purpose, expires_at=now() + timedelta(hours=hours),
    ))
    subject = "Reset your A11yra password" if purpose == "reset" else "Verify your A11yra email"
    tasks.add_task(send_mail, request, user.email, subject,
                   f"{request.app.state.public_url}/account/{purpose}#token={raw}\nThis link expires in {hours} hour(s).")


@router.get("/csrf")
def csrf(request: Request, response: Response, db=Depends(get_db)):
    existing = request.cookies.get(CSRF, "")
    if valid_csrf_cookie(request, existing):
        return {"csrf_token": existing}
    value = existing.partition(".")[0]
    try:
        session = current_session(request, db, refresh=True)
    except ApiError:
        session = None
    if session and session.csrf_hash == digest(value):
        return {"csrf_token": csrf_cookie(request, response, value)}
    return {"csrf_token": csrf_cookie(request, response)}


@router.post("/signup", status_code=202)
def signup(body: Credentials, request: Request, tasks: BackgroundTasks, db=Depends(get_db)):
    validate_csrf(request)
    request.app.state.auth_limits.hit(("signup", request.client.host), 5, 3600)
    if len(body.password) < 12:
        raise ApiError(422, "password_length", "Use at least 12 characters for your password.")
    user = User(email=body.email, password_hash=hasher.hash(body.password))
    result = {"message": "If this email can be registered, check your inbox for a verification link. You can sign in now."}
    if request.app.state.mailer.disabled:
        result = {"message": "You can sign in now. This temporary demo does not send email."}
    try:
        db.add(user)
        db.flush()
        workspace = Workspace(name="Personal workspace", personal_owner_id=user.id)
        db.add(workspace)
        db.flush()
        db.add_all([
            Membership(workspace_id=workspace.id, user_id=user.id, role="owner"),
            Subscription(workspace_id=workspace.id),
        ])
        log_event(db, "signup", "account", request=request, workspace=workspace.id, actor=user.id, target=user.id)
        schedule_link(db, request, tasks, user, "verify")
        db.commit()
    except IntegrityError:
        db.rollback()
        tasks.tasks.clear()
    return result


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db=Depends(get_db)):
    validate_csrf(request)
    limiter = request.app.state.auth_limits
    limiter.hit(("login_ip", request.client.host), 20, 60)
    identity = digest(body.email)
    user = db.scalar(select(User).where(User.email == body.email))
    blocked = limiter.check_login(identity)
    password_ok = False if blocked else verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not password_ok:
        if not blocked:
            limiter.login_result(identity, False)
        log_event(db, "login_failed", "account", request=request,
                  workspace=personal_workspace(db, user.id) if user else None)
        db.commit()
        raise ApiError(401, "invalid_login", "Unable to sign in with those details. Wait a little before trying again.")
    limiter.login_result(identity, True)
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(body.password)
    log_event(db, "login_success", "account", request=request, workspace=personal_workspace(db, user.id),
              actor=user.id, target=user.id)
    open_session(db, request, response, user)
    return profile(db, user)


@router.get("/me")
def me(request: Request, db=Depends(get_db)):
    return profile(db, signed_in(request, db))


@router.post("/refresh", status_code=204)
def refresh(request: Request, response: Response, db=Depends(get_db)):
    session = current_session(request, db, refresh=True)
    validate_csrf(request, session)
    access, refresh_token = token(), token()
    updated = db.execute(update(Session).where(
        Session.id == session.id, Session.refresh_hash == session.refresh_hash, Session.expires_at > now(),
    ).values(access_hash=digest(access), refresh_hash=digest(refresh_token),
             access_until=now() + timedelta(seconds=ACCESS_SECONDS)))
    if updated.rowcount != 1:
        raise ApiError(401, "sign_in_required", "Sign in to continue.")
    db.commit()
    remaining = max(0, int((session.expires_at - now()).total_seconds()))
    session_cookies(request, response, access, refresh_token, request.cookies[CSRF].split(".")[0], remaining)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db=Depends(get_db)):
    validate_csrf(request)
    try:
        session = current_session(request, db, refresh=True)
    except ApiError:
        session = None
    if session:
        validate_csrf(request, session)
        log_event(db, "logout", "account", request=request, workspace=personal_workspace(db, session.user_id),
                  actor=session.user_id, target=session.user_id)
        db.delete(session)
        db.commit()
    clear_cookies(request, response)


@router.post("/forgot", status_code=202)
def forgot(body: EmailInput, request: Request, tasks: BackgroundTasks, db=Depends(get_db)):
    validate_csrf(request)
    limiter = request.app.state.auth_limits
    limiter.hit(("reset_ip", request.client.host), 10, 3600)
    limiter.hit(("reset_email", digest(body.email)), 3, 3600)
    user = db.scalar(select(User).where(User.email == body.email))
    if user:
        schedule_link(db, request, tasks, user, "reset")
        db.commit()
    return {"message": "If there is an account with that email, a reset link will arrive shortly."}


def consume(db, raw, purpose):
    match = db.execute(delete(AccountToken).where(
        AccountToken.digest == digest(raw), AccountToken.expires_at > now(), AccountToken.purpose == purpose,
    ).returning(AccountToken.user_id)).scalar_one_or_none()
    if not match:
        raise ApiError(400, "link_invalid", "This link has expired or has already been used.")
    return db.get(User, match)


@router.post("/reset", status_code=204)
def reset(body: PasswordReset, request: Request, db=Depends(get_db)):
    validate_csrf(request)
    request.app.state.auth_limits.hit(("reset_submit", request.client.host), 10, 3600)
    user = consume(db, body.token, "reset")
    user.password_hash = hasher.hash(body.password)
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.execute(delete(AccountToken).where(AccountToken.user_id == user.id, AccountToken.purpose == "reset"))
    log_event(db, "password_changed", "account", request=request, workspace=personal_workspace(db, user.id),
              actor=user.id, target=user.id)
    db.commit()


@router.post("/verify", status_code=204)
def verify(body: LinkToken, request: Request, db=Depends(get_db)):
    validate_csrf(request)
    request.app.state.auth_limits.hit(("verify_submit", request.client.host), 10, 3600)
    user = consume(db, body.token, "verify")
    user.email_verified = True
    db.commit()


@router.post("/verify/resend", status_code=202)
def resend_verification(request: Request, tasks: BackgroundTasks, db=Depends(get_db)):
    user = signed_in(request, db)
    request.app.state.auth_limits.hit(("verify_resend", user.id), 3, 3600)
    if not user.email_verified:
        schedule_link(db, request, tasks, user, "verify")
        db.commit()
    return {"message": "Check your inbox for a verification link."}


@router.get("/data")
def export_data(request: Request, response: Response, db=Depends(get_db)):
    user = signed_in(request, db)
    response.headers["Content-Disposition"] = 'attachment; filename="a11yra-account.json"'
    docs = list(db.scalars(select(Document).where(Document.uploaded_by == user.id)))
    return {
        "profile": profile(db, user), "created_at": user.created_at,
        "documents": [
            {"id": doc.id, "workspace_id": doc.workspace_id, "filename": doc.filename,
             "size": doc.size, "status": doc.status, "created_at": doc.created_at, "expires_at": doc.expires_at,
             "audits": [{"id": audit.id, "created_at": audit.created_at, "summary": audit.summary,
                         "findings": audit.findings} for audit in db.scalars(
                             select(AuditRecord).where(AuditRecord.document_id == doc.id))]}
            for doc in docs
        ],
        "activity": [{"action": row.action, "created_at": row.created_at, "workspace_id": row.workspace_id}
                     for row in db.scalars(select(AuditLog).where(AuditLog.actor_user_id == user.id))],
    }


@router.delete("/account", status_code=204)
def delete_account(body: ConfirmDeletion, request: Request, response: Response, db=Depends(get_db)):
    from app.product.retention import remove_content, revoke_share

    user = signed_in(request, db)
    request.app.state.auth_limits.hit(("delete_account", user.id), 5, 3600)
    if not body.confirm or not verify_password(body.password, user.password_hash):
        raise ApiError(400, "delete_confirmation", "Confirm the deletion and enter your current password.")
    workspace = personal_workspace(db, user.id)
    docs = list(db.scalars(select(Document).where(
        (Document.uploaded_by == user.id) | (Document.workspace_id == workspace)
    )))
    for doc in docs:
        remove_content(db, request.app.state, doc, shares=True)
    for share in db.scalars(select(ReaderShare).where(ReaderShare.created_by == user.id)):
        revoke_share(db, request.app.state, share)
    # Remove invitations addressed to the account and anonymize retained security records.
    db.execute(delete(Invite).where(Invite.email == user.email))
    db.execute(update(AuditLog).where(AuditLog.actor_user_id == user.id).values(
        actor_user_id=None, ip_hash=None, user_agent_short=None,
    ))
    if workspace is not None:
        db.execute(update(AuditLog).where(AuditLog.workspace_id == workspace, AuditLog.action == "login_failed")
                   .values(ip_hash=None, user_agent_short=None))
    db.execute(update(AuditLog).where(AuditLog.target_type.in_(("account", "member")), AuditLog.target_id == user.id)
               .values(target_id=None))
    log_event(db, "account_deleted", "account")
    db.delete(user)
    db.commit()
    clear_cookies(request, response)
