import hashlib
import hmac
import os
import re
import secrets
from collections import OrderedDict
from threading import Lock
from time import monotonic

from fastapi import Request, Response
from sqlalchemy import select

from app.core.errors import ApiError
from app.product.db import now
from app.product.tables import AuditLog, Session, User

ACCESS = "a11yra_access"
REFRESH = "a11yra_refresh"
CSRF = "a11yra_csrf"
ACCESS_SECONDS = 900
REFRESH_SECONDS = 7 * 86400
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


def token() -> str:
    return secrets.token_urlsafe(32)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fingerprint(request: Request) -> str:
    address = request.client.host if request.client else "unknown"
    return hmac.new(request.app.state.secret, address.encode(), "sha256").hexdigest()


class RateLimiter:
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = Lock()

    def hit(self, key, limit, window):
        current = monotonic()
        with self.lock:
            entry = self.entries.get(key)
            count, deadline = entry if entry and entry[1] > current else (0, current + window)
            if count >= limit:
                raise ApiError(429, "rate_limit", "Too many requests. Wait a little and try again.")
            self.entries[key] = (count + 1, deadline)
            self.entries.move_to_end(key)
            if len(self.entries) > 20000:
                self.entries.popitem(last=False)

    def check_login(self, identity):
        current = monotonic()
        with self.lock:
            _, unlock, expires = self.entries.get(("login", identity), (0, 0, 0))
            return expires > current and unlock > current

    def login_result(self, identity, success):
        key = ("login", identity)
        current = monotonic()
        with self.lock:
            if success:
                self.entries.pop(key, None)
                return
            failures, _, expires = self.entries.get(key, (0, 0, 0))
            failures = (failures if expires > current else 0) + 1
            delay = min(2 ** min(failures - 4, 8), 300) if failures >= 5 else 0
            self.entries[key] = (failures, current + delay, current + 900)
            self.entries.move_to_end(key)
            if len(self.entries) > 20000:
                self.entries.popitem(last=False)


def csrf_signature(request: Request, value: str) -> str:
    return hmac.new(request.app.state.secret, value.encode(), "sha256").hexdigest()


def csrf_cookie(request: Request, response: Response, value: str | None = None) -> str:
    value = value or token()
    signed = f"{value}.{csrf_signature(request, value)}"
    set_cookie(request, response, CSRF, signed, REFRESH_SECONDS)
    return signed


def set_cookie(request: Request, response: Response, name, value, max_age):
    response.set_cookie(name, value, max_age=max_age, httponly=name != CSRF,
                        secure=request.app.state.secure_cookies, samesite="lax", path="/")


def clear_cookies(request: Request, response: Response):
    for name in (ACCESS, REFRESH, CSRF):
        set_cookie(request, response, name, "", 0)


def valid_csrf_cookie(request: Request, cookie: str) -> bool:
    value, _, signature = cookie.partition(".")
    return (len(cookie) == 108 and TOKEN_PATTERN.fullmatch(value) is not None and signature.isascii()
            and hmac.compare_digest(csrf_signature(request, value), signature))


def validate_csrf(request: Request, session: Session | None = None):
    cookie = request.cookies.get(CSRF, "")
    header = request.headers.get("x-csrf-token", "")
    origin = request.headers.get("origin")
    if (origin and origin not in request.app.state.origins
            or not valid_csrf_cookie(request, cookie) or not header.isascii()
            or not hmac.compare_digest(cookie, header)
            or session is not None and session.csrf_hash != digest(cookie.split(".")[0])):
        raise ApiError(403, "csrf_failed", "Refresh the page and try again.")


def current_session(request: Request, db, refresh=False) -> Session:
    raw = request.cookies.get(REFRESH if refresh else ACCESS, "")
    if TOKEN_PATTERN.fullmatch(raw):
        field = Session.refresh_hash if refresh else Session.access_hash
        session = db.scalar(select(Session).where(field == digest(raw), Session.expires_at > now()))
        if session and (refresh or session.access_until > now()):
            return session
    raise ApiError(401, "sign_in_required", "Sign in to continue.")


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db


def signed_in(request: Request, db) -> User:
    session = current_session(request, db)
    request.app.state.user_limits.hit(session.user_id, 240, 60)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        validate_csrf(request, session)
    user = db.get(User, session.user_id)
    if not user:
        raise ApiError(401, "sign_in_required", "Sign in to continue.")
    return user


def log_event(db, action, target_type, *, request=None, workspace=None, actor=None, target=None, metadata=None):
    db.add(AuditLog(
        workspace_id=workspace, actor_user_id=actor, action=action, target_type=target_type,
        target_id=target, ip_hash=fingerprint(request) if request else None,
        user_agent_short=clean_agent(request) if request else None,
        metadata_json=metadata or {},
    ))


def clean_agent(request):
    return re.sub(r"[^ -~]", "", request.headers.get("user-agent", ""))[:120]


def app_secret() -> bytes:
    value = os.getenv("A11YRA_SECRET")
    if os.getenv("A11YRA_ENV", "dev") != "dev" and (not value or len(value) < 32):
        raise RuntimeError("Set A11YRA_SECRET to at least 32 random characters.")
    return value.encode() if value else secrets.token_bytes(32)
