import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.api.routes import apply_document_fixes, router
from app.core.config import MAX_MULTIPART_BYTES, SESSION_SWEEP_SECONDS, TEMP_ROOT
from app.core.errors import ApiError
from app.core.storage import DocumentStore
from app.core.validation import upload_too_large


async def expire_sessions(store: DocumentStore) -> None:
    while True:
        await asyncio.sleep(SESSION_SWEEP_SECONDS)
        # Retry on the next sweep if a file is temporarily locked.
        with suppress(OSError):
            await asyncio.to_thread(store.expire_old_sessions)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with TemporaryDirectory(prefix="a11yra-", dir=TEMP_ROOT) as root:
        store = DocumentStore(Path(root))
        app.state.documents = store
        sweeper = asyncio.create_task(expire_sessions(store))
        try:
            yield
        finally:
            sweeper.cancel()
            with suppress(asyncio.CancelledError):
                await sweeper


app = FastAPI(title="A11yra", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def reject_oversized_multipart(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/documents":
        length = request.headers.get("content-length")
        if length is not None and int(length) > MAX_MULTIPART_BYTES:
            return upload_too_large().response()
    return await call_next(request)


@app.exception_handler(ApiError)
async def handle_api_error(_request: Request, error: ApiError):
    return error.response()


@app.exception_handler(RequestValidationError)
async def handle_invalid_request(request: Request, error: RequestValidationError):
    if request.scope.get("endpoint") is apply_document_fixes:
        if any(item["type"] == "literal_error" and item["loc"][-1] == "type" for item in error.errors()):
            return ApiError(422, "fix_not_supported", "Choose a supported repair type.").response()
        return ApiError(422, "fix_invalid", "Send a list of fixes with a valid payload for each finding.").response()
    return ApiError(422, "invalid_file_type", "Attach a .docx file in the file field.").response()


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
