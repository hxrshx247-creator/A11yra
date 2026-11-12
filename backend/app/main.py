import asyncio
import hmac
import logging
import os
from collections import Counter
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from threading import BoundedSemaphore

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.api.routes import apply_document_fixes, router
from app.core.config import SESSION_SWEEP_SECONDS
from app.core.errors import ApiError
from app.core.storage import DocumentStore
from app.export.learner_reader import _csp_hash
from app.product import auth, billing, documents, integration, workspaces
from app.product.db import ROOT, build_engine, database_url, sessions
from app.product.http import ProductHTTP
from app.product.mail import Mailer
from app.product.retention import cleanup, send_expiry_notices
from app.product.security import RateLimiter, app_secret

DEFAULT_ORIGINS = "http://127.0.0.1:5173,http://localhost:5173"


def public_url():
    render_url = os.getenv("RENDER_EXTERNAL_URL") if os.getenv("A11YRA_ENV") == "demo" else None
    return os.getenv("A11YRA_PUBLIC_URL", render_url or "http://127.0.0.1:5173").rstrip("/")


def allowed_origins():
    environment = os.getenv("A11YRA_ENV", "dev")
    defaults = {"dev": DEFAULT_ORIGINS, "demo": public_url()}.get(environment, "")
    return [origin.strip().rstrip("/") for origin in os.getenv("A11YRA_CORS_ORIGINS", defaults).split(",")
            if origin.strip()]


async def sweep(state):
    while True:
        await asyncio.sleep(SESSION_SWEEP_SECONDS)
        try:
            await asyncio.to_thread(cleanup, state)
            await asyncio.to_thread(send_expiry_notices, state)
        except (OSError, SQLAlchemyError):
            state.logger.warning('{"event":"retention_sweep_failed"}')


def set_up_database(engine, environment):
    config = Config(ROOT / "backend" / "alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        if environment == "dev":
            command.upgrade(config, "head")
        elif MigrationContext.configure(connection).get_current_heads() != tuple(ScriptDirectory.from_config(config).get_heads()):
            raise RuntimeError("Run Alembic migrations before starting A11yra.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = app.state
    environment = os.getenv("A11YRA_ENV", "dev")
    state.logger = logging.getLogger("a11yra")
    state.logger.setLevel(logging.INFO)
    if not state.logger.handlers:
        state.logger.addHandler(logging.StreamHandler())
    state.logger.propagate = False
    state.origins = set(allowed_origins())
    state.public_url = public_url()
    if environment != "dev" and (not state.public_url.startswith("https://") or state.public_url not in state.origins):
        raise RuntimeError("Set an HTTPS A11YRA_PUBLIC_URL and include it in A11YRA_CORS_ORIGINS.")
    state.secure_cookies = environment != "dev" or state.public_url.startswith("https://")
    state.secret = app_secret()
    state.file_hours = int(os.getenv("A11YRA_FILE_HOURS", "24"))
    state.audit_days = int(os.getenv("A11YRA_AUDIT_DAYS", "30"))
    if state.file_hours < 1 or state.audit_days < 1:
        raise RuntimeError("Retention values must be positive.")
    state.mailer = Mailer(environment)
    state.billing = billing.Billing(environment)
    state.ip_limits, state.user_limits, state.auth_limits = RateLimiter(), RateLimiter(), RateLimiter()
    state.ip_requests_per_minute = max(1, int(os.getenv("A11YRA_IP_REQUESTS_PER_MINUTE", "180")))
    state.public_audit_timeout = 30
    state.public_audit_slots = BoundedSemaphore(4)
    state.requests = Counter()
    state.report_error = None
    if dsn := os.getenv("A11YRA_SENTRY_DSN"):
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, environment=environment, default_integrations=False, send_default_pii=False)
        state.report_error = sentry_sdk.capture_message
    root = Path(os.getenv("A11YRA_DATA_DIR", str(ROOT / "backend" / ".a11yra-data")))
    files = root / "documents"
    state.shares_root = root / "readers"
    for directory in (root, files, state.shares_root):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    state.documents = DocumentStore(files, state.file_hours * 3600)
    state.engine = build_engine(database_url())
    try:
        set_up_database(state.engine, environment)
        state.sessions = sessions(state.engine)
        cleanup(state)
        sweeper = asyncio.create_task(sweep(state))
        try:
            yield
        finally:
            sweeper.cancel()
            with suppress(asyncio.CancelledError):
                await sweeper
    finally:
        state.engine.dispose()


app = FastAPI(title="A11yra", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")
for routes in (router, auth.router, workspaces.router, documents.router, billing.router, integration.router):
    app.include_router(routes)
app.add_middleware(ProductHTTP)
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins(), allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Content-Type", "X-CSRF-Token", "X-Workspace-ID", "Authorization"])


@app.get("/api/docs", include_in_schema=False)
def api_docs():
    response = get_swagger_ui_html(openapi_url="/api/openapi.json", title="A11yra API reference",
                                   swagger_favicon_url="/favicon.svg")
    page = BeautifulSoup(response.body, "html.parser", from_encoding="utf-8")
    hashes = " ".join(_csp_hash(script.string) for script in page.find_all("script") if script.string)
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; script-src https://cdn.jsdelivr.net {hashes}; "
        "style-src https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data:; "
        "frame-ancestors 'none'; object-src 'none'; base-uri 'none'"
    )
    return response


@app.get("/api/ready")
def ready(request: Request):
    from sqlalchemy import text

    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        if not request.app.state.documents.root.is_dir() or not request.app.state.shares_root.is_dir():
            raise OSError
    except (OSError, SQLAlchemyError):
        raise ApiError(503, "not_ready", "The service is temporarily unavailable.") from None
    return {"status": "ready"}


@app.get("/api/metrics", include_in_schema=False)
def metrics(request: Request):
    expected = os.getenv("A11YRA_METRICS_TOKEN", "")
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
        raise ApiError(404, "route_not_found", "This page or endpoint could not be found.")
    lines = ["# TYPE a11yra_http_requests_total counter"]
    for status, count in sorted(request.app.state.requests.items()):
        lines.append(f'a11yra_http_requests_total{{status="{status}"}} {count}')
    return Response("\n".join(lines) + "\n", media_type="text/plain")


@app.exception_handler(ApiError)
async def handle_api_error(_request: Request, error: ApiError):
    return error.response()


@app.exception_handler(RequestValidationError)
async def handle_invalid_request(request: Request, error: RequestValidationError):
    if request.scope.get("endpoint") is apply_document_fixes:
        if any(item["type"] == "literal_error" and item["loc"][-1] == "type" for item in error.errors()):
            return ApiError(422, "fix_not_supported", "Choose a supported repair type.").response()
        return ApiError(422, "fix_invalid", "Send a list of fixes with a valid payload for each finding.").response()
    if request.url.path in {"/api/documents", "/api/public/v1/audit"}:
        return ApiError(422, "invalid_file_type", "Attach a .docx file in the file field.").response()
    return ApiError(422, "invalid_request", "Check the form fields and try again.").response()


@app.exception_handler(HTTPException)
async def handle_http_error(_request: Request, error: HTTPException):
    code, message = {
        400: ("invalid_file_type", "Send the document as a file upload."),
        404: ("route_not_found", "This page or endpoint could not be found."),
        405: ("method_not_allowed", "This endpoint does not support that request method."),
    }.get(error.status_code, ("request_failed", "The server could not process the request."))
    response = ApiError(error.status_code, code, message).response()
    response.headers.update(error.headers or {})
    return response


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        if Path(path).parts[:1] in {("api",), ("r",)}:
            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or Path(path).suffix:
                raise
            return await super().get_response("index.html", scope)


if frontend_dir := os.getenv("A11YRA_FRONTEND_DIR"):
    app.mount("/", FrontendFiles(directory=frontend_dir, html=True), name="frontend")
