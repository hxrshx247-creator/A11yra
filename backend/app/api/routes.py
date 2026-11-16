from datetime import timedelta
from contextlib import suppress
from io import BytesIO
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from docx import Document as WordDocument

from app.audit.reaudit import reaudit_document
from app.audit.runner import run_audit
from app.audit.score import calculate_progress
from app.audit.reader_preview import build_reader_preview
from app.core.config import DOCX_MIME
from app.core.errors import ApiError
from app.core.validation import read_docx
from app.export.docx_export import ExportPendingVerification, InvalidExport, prepare_docx_export
from app.export.html_export import convert_docx_to_html
from app.export.page_preview import MAX_PAGES, bundled_preview, render_preview_pages
from app.export.learner_download import prepare_learner_download
from app.models import Audit, FixRequest, FixResponse, ReaderPreview, ReauditResponse, UploadResponse
from app.repair.service import repair_document
from app.product.db import now
from app.product.documents import record_audit, record_export
from app.product.plans import check_upload, lock_workspace, workspace_plan
from app.product.retention import remove_content
from app.product.security import get_db, log_event
from app.product.tables import Document, FixRecord, UsageEvent
from app.product.workspaces import require_role

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
    request: Request, response: Response, file: Annotated[UploadFile, File()],
    context=Depends(require_role("editor")), db=Depends(get_db),
) -> UploadResponse:
    return save_upload(request, response, file, context, db)


@router.post("/documents/sample", status_code=201)
def sample_document(request: Request, response: Response, kind: str = "syllabus", context=Depends(require_role("editor")),
                    db=Depends(get_db)) -> UploadResponse:
    if kind not in {"syllabus", "lecture", "messy"}:
        raise ApiError(422, "invalid_sample", "Choose the lecture, syllabus, or messy handout sample.")
    fixture_name = "pilot-syllabus.docx" if kind == "syllabus" else "stack-queue-lecture.docx"
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / fixture_name
    from starlette.datastructures import Headers

    with fixture.open("rb") as source:
        filename = "Sample syllabus.docx" if kind == "syllabus" else "Stack and Queue lecture.docx"
        file = UploadFile(source, filename=filename, headers=Headers({"content-type": DOCX_MIME}))
        return save_upload(request, response, file, context, db)


def save_upload(request, response, file, context, db):
    user, workspace, _ = context
    filename, contents, document = read_docx(file)
    check_upload(db, workspace, len(contents))
    document_id = uuid4()
    audit = run_audit(document, document_id, filename)
    current = now()
    state = request.app.state
    plan = workspace_plan(db, workspace)
    try:
        state.documents.save(document_id, contents, audit)
    except OSError:
        raise ApiError(500, "storage_failed", "The server could not save the document. Try again.") from None
    try:
        db.add(Document(
            id=str(document_id), workspace_id=workspace, uploaded_by=user.id, filename=filename, size=len(contents),
            expires_at=current + timedelta(hours=state.file_hours),
            history_until=current + max(timedelta(hours=state.file_hours),
                                        timedelta(days=min(state.audit_days, plan.history_days))),
        ))
        db.flush()
        record_audit(db, audit)
        db.add(UsageEvent(workspace_id=workspace, kind="audit"))
        for action in ("document_uploaded", "audit_run"):
            log_event(db, action, "document", request=request, workspace=workspace, actor=user.id, target=str(document_id))
        db.commit()
    except Exception:
        state.documents.purge(document_id)
        raise
    response.headers["Cache-Control"] = "no-store"
    return UploadResponse(document_id=document_id, filename=filename, audit=audit)


@router.get("/documents/{id}/audit")
def get_audit(id: str, request: Request, response: Response,
              _context=Depends(require_role("viewer", document=True, active=True))) -> Audit:
    document_id = parse_document_id(id)
    try:
        audit = request.app.state.documents.load_audit(document_id)
    except (OSError, ValueError):
        raise ApiError(500, "storage_failed", "The server could not read the audit. Try uploading the document again.") from None
    if audit is None:
        raise document_not_found()
    response.headers["Cache-Control"] = "no-store"
    return audit


@router.post("/documents/{id}/findings/{finding_id}/dismiss", status_code=204)
def dismiss_heading_candidate(id: str, finding_id: str, request: Request, response: Response,
                              _context=Depends(require_role("editor", document=True, active=True))) -> Response:
    document_id = parse_document_id(id)
    store = request.app.state.documents
    with store.locked_session(document_id) as session:
        if session is None:
            raise document_not_found()
        state = store.current_state(session)
        audit = store.read_audit(state)
        finding = next((item for item in audit.findings if item.id == finding_id), None)
        if finding is None or not finding.id.startswith("heading-lookalike-") or finding.status != "needs_review":
            raise ApiError(409, "finding_not_dismissible", "Only an unreviewed heading candidate can be dismissed.")
        finding.status = "dismissed"
        check = next((item for item in audit.checks if item.id == "headings"), None)
        if check is not None:
            check.finding_ids = [item.id for item in audit.findings if item.check_id == "headings" and item.status != "dismissed"]
            if not check.finding_ids:
                check.result = "passed"
                check.summary = "Heading structure reviewed by the teacher."
        audit.progress = calculate_progress(audit.checks)
        store.save_audit(state, audit)
    response.headers["Cache-Control"] = "no-store"
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/documents/{id}/preview")
def document_preview(id: str, request: Request, response: Response, layout: bool = False,
                     annotated: bool = False,
                     context=Depends(require_role("viewer", document=True, active=True))) -> dict:
    document_id = parse_document_id(id)
    store = request.app.state.documents
    _, _, document = context
    cache_name = "flagged-preview.json" if annotated else "layout-preview.json"
    cached = {}
    try:
        with store.locked_session(document_id) as session:
            if session is None:
                raise document_not_found()
            state = store.current_state(session)
            contents = (state / "working.docx").read_bytes()
            flags = [finding for finding in store.read_audit(state).findings
                     if finding.status in {"open", "needs_review"}] if annotated else None
            if layout:
                with suppress(OSError, ValueError):
                    cached = json.loads((state / cache_name).read_bytes())
        flag_ids = [finding.id for finding in flags or []]
        pages, positions = [], {}
        if layout:
            if cached.get("flags") == flag_ids:
                pages, positions = cached["pages"], cached["positions"]
            else:
                bundled = bundled_preview(contents, flags)
                pages, positions = bundled if bundled is not None else render_preview_pages(contents, flags)
                if pages and bundled is None:
                    with store.locked_session(document_id) as session:
                        if session is not None and store.current_state(session) == state:
                            with suppress(OSError):
                                (state / cache_name).write_text(
                                    json.dumps({"flags": flag_ids, "pages": pages, "positions": positions}),
                                    encoding="utf-8",
                                )
        html = "" if pages else convert_docx_to_html(contents, flags=flags)
    except (OSError, ValueError):
        raise ApiError(500, "preview_failed", "The document preview could not be prepared.") from None
    response.headers["Cache-Control"] = "no-store"
    result = {"filename": document.filename, "html": html}
    if layout:
        return {**result, "pages": pages[:MAX_PAGES], "truncated": len(pages) > MAX_PAGES, "positions": positions}
    return result


@router.get("/documents/{id}/reader-preview", response_model=ReaderPreview)
def reader_preview(id: str, request: Request, response: Response, version: str = "original",
                  _context=Depends(require_role("viewer", document=True, active=True))) -> ReaderPreview:
    if version not in {"original", "repaired"}:
        raise ApiError(422, "invalid_version", "Choose original or repaired preview.")
    document_id = parse_document_id(id)
    store = request.app.state.documents
    with store.locked_session(document_id) as session:
        if session is None:
            raise document_not_found()
        state = store.current_state(session)
        audit = store.read_audit(state)
        path = session / "original.docx" if version == "original" else state / "working.docx"
        try:
            document = WordDocument(BytesIO(path.read_bytes()))
            result = build_reader_preview(document, audit, version)
        except (OSError, ValueError):
            raise ApiError(500, "preview_failed", "The screen reader preview could not be prepared.") from None
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/documents/{id}/fixes")
def apply_document_fixes(id: str, fixes: FixRequest, request: Request, response: Response,
                         context=Depends(require_role("editor", document=True, active=True)),
                         db=Depends(get_db)) -> FixResponse:
    document_id = parse_document_id(id)
    user, workspace, doc = context
    lock_workspace(db, workspace)
    try:
        result = repair_document(request.app.state.documents, document_id, fixes.fixes)
    except (OSError, ValueError):
        raise ApiError(500, "storage_failed", "The server could not save the repairs. Try again.") from None
    if result is None:
        raise document_not_found()
    if result.applied:
        db.add(FixRecord(document_id=doc.id, actor_user_id=user.id,
                         result={"applied": [fix.finding_id for fix in result.applied]}))
        log_event(db, "fix_applied", "document", request=request, workspace=workspace, actor=user.id,
                  target=doc.id, metadata={"count": len(result.applied)})
        db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/documents/{id}/reaudit")
def reaudit(id: str, request: Request, response: Response,
            context=Depends(require_role("editor", document=True, active=True)), db=Depends(get_db)) -> ReauditResponse:
    document_id = parse_document_id(id)
    user, workspace, doc = context
    lock_workspace(db, workspace)
    try:
        result = reaudit_document(request.app.state.documents, document_id, doc.filename)
    except (OSError, ValueError):
        raise ApiError(500, "storage_failed", "The server could not run a new audit. Try again.") from None
    if result is None:
        raise document_not_found()
    record_audit(db, result.audit)
    log_event(db, "reaudit", "document", request=request, workspace=workspace, actor=user.id, target=doc.id)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/documents/{id}/export/docx",
    response_class=Response,
    responses={200: {"content": {DOCX_MIME: {"schema": {"type": "string", "format": "binary"}}}}},
)
def export_docx(id: str, request: Request,
                context=Depends(require_role("viewer", document=True, active=True)), db=Depends(get_db)) -> Response:
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

    record_export(db, request, context, "docx")
    return Response(
        content=result,
        media_type=DOCX_MIME,
        headers={
            "Content-Disposition": 'attachment; filename="a11yra-repaired.docx"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/documents/{id}/export/html",
    response_class=Response,
    responses={200: {"content": {
        "text/html": {"schema": {"type": "string"}},
        "application/zip": {"schema": {"type": "string", "format": "binary"}},
    }}},
)
def export_learner(id: str, request: Request, offline: bool = False,
                   context=Depends(require_role("viewer", document=True, active=True)), db=Depends(get_db)) -> Response:
    document_id = parse_document_id(id)
    store = request.app.state.documents
    try:
        result = prepare_learner_download(store, document_id, offline)
    except ExportPendingVerification:
        raise ApiError(409, "export_failed", "Run a new audit to verify applied fixes before downloading.") from None
    except (OSError, ValueError, InvalidExport):
        raise ApiError(500, "export_failed", "The server could not prepare the learner download.") from None
    if result is None:
        raise document_not_found()

    record_export(db, request, context, "reader_html" if offline else "reader_zip")
    filename = "a11yra-reader.html" if offline else "a11yra-reader.zip"
    return Response(
        content=result,
        media_type="text/html" if offline else "application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/documents/{id}", status_code=204)
def delete_document(id: str, request: Request,
                    context=Depends(require_role("editor", document=True)), db=Depends(get_db)) -> Response:
    user, workspace, doc = context
    lock_workspace(db, workspace)
    try:
        remove_content(db, request.app.state, doc, shares=True)
    except OSError:
        raise ApiError(500, "storage_failed", "The server could not remove this upload. Try again.") from None
    log_event(db, "document_deleted", "document", request=request, workspace=workspace, actor=user.id, target=doc.id)
    db.delete(doc)
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
