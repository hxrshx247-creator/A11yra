from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Request, Response, UploadFile
from starlette.background import BackgroundTask

from app.audit.reaudit import reaudit_document
from app.audit.runner import run_audit
from app.core.config import DOCX_MIME
from app.core.errors import ApiError
from app.core.validation import read_docx
from app.export.docx_export import ExportPendingVerification, InvalidExport, prepare_docx_export
from app.models import Audit, FixRequest, FixResponse, ReauditResponse, UploadResponse
from app.repair.service import repair_document

router = APIRouter(prefix="/api")


def document_not_found() -> ApiError:
    return ApiError(404, "document_not_found", "This document could not be found. Upload it again to run a new audit.")


def parse_document_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise document_not_found() from None


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/documents", status_code=201)
def upload_document(
    request: Request, response: Response, file: Annotated[UploadFile, File()]
) -> UploadResponse:
    filename, contents, document = read_docx(file)
    document_id = uuid4()
    audit = run_audit(document, document_id)
    try:
        request.app.state.documents.save(document_id, contents, audit)
    except OSError:
        raise ApiError(500, "storage_failed", "The server could not save the document. Try again.") from None
    response.headers["Cache-Control"] = "no-store"
    return UploadResponse(document_id=document_id, filename=filename, audit=audit)


@router.get("/documents/{id}/audit")
def get_audit(id: str, request: Request, response: Response) -> Audit:
    document_id = parse_document_id(id)
    try:
        audit = request.app.state.documents.load_audit(document_id)
    except (OSError, ValueError):
        raise ApiError(500, "storage_failed", "The server could not read the audit. Try uploading the document again.") from None
    if audit is None:
        raise document_not_found()
    response.headers["Cache-Control"] = "no-store"
    return audit


@router.post("/documents/{id}/fixes")
def apply_document_fixes(id: str, fixes: FixRequest, request: Request, response: Response) -> FixResponse:
    document_id = parse_document_id(id)
    try:
        result = repair_document(request.app.state.documents, document_id, fixes.fixes)
    except (OSError, ValueError):
        raise ApiError(500, "storage_failed", "The server could not save the repairs. Try again.") from None
    if result is None:
        raise document_not_found()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/documents/{id}/reaudit")
def reaudit(id: str, request: Request, response: Response) -> ReauditResponse:
    document_id = parse_document_id(id)
    try:
        result = reaudit_document(request.app.state.documents, document_id)
    except (OSError, ValueError):
        raise ApiError(500, "storage_failed", "The server could not run a new audit. Try again.") from None
    if result is None:
        raise document_not_found()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/documents/{id}/export/docx",
    response_class=Response,
    responses={200: {"content": {DOCX_MIME: {"schema": {"type": "string", "format": "binary"}}}}},
)
def export_docx(id: str, request: Request) -> Response:
    document_id = parse_document_id(id)
    store = request.app.state.documents
    try:
        result = prepare_docx_export(store, document_id)
    except ExportPendingVerification:
        raise ApiError(409, "export_failed", "Run a new audit to verify applied fixes before downloading.") from None
    except (OSError, ValueError, InvalidExport):
        raise ApiError(500, "export_failed", "The server could not prepare a valid Word document for download.") from None
    if result is None:
        raise document_not_found()

    contents, session = result
    return Response(
        content=contents,
        media_type=DOCX_MIME,
        headers={
            "Content-Disposition": 'attachment; filename="a11yra-repaired.docx"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(store.remove_retired_session, session),
    )


@router.delete("/documents/{id}", status_code=204)
def delete_document(id: str, request: Request) -> Response:
    document_id = parse_document_id(id)
    try:
        deleted = request.app.state.documents.delete(document_id)
    except OSError:
        raise ApiError(500, "storage_failed", "The server could not remove this upload. Try again.") from None
    if not deleted:
        raise document_not_found()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
