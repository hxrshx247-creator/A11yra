from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import quote
from uuid import UUID

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import ApiError
from app.export.docx_export import ExportPendingVerification, InvalidExport
from app.export.learner_download import prepare_learner_download
from app.export.learner_reader import published_reader_policy
from app.product.db import now
from app.product.plans import lock_workspace, workspace_plan
from app.product.retention import revoke_share, share_path
from app.product.security import TOKEN_PATTERN, digest, get_db, log_event, token
from app.product.tables import AuditRecord, Document, ExportRecord, ReaderShare, UsageEvent
from app.product.workspaces import csv_response, document_not_found, require_role

router = APIRouter(tags=["Document history and sharing"])


def record_audit(db, audit):
    summary = audit.model_dump(mode="json", exclude={"findings"})
    findings = [finding.model_dump(mode="json", exclude={"preview", "locator"}) for finding in audit.findings]
    for finding in findings:
        finding["evidence"] = finding["evidence"][:240]
        finding["location"] = finding["location"][:160]
    db.add(AuditRecord(id=str(audit.audit_id), document_id=str(audit.document_id), summary=summary, findings=findings))


def record_export(db, request, context, format):
    actor, workspace, doc = context
    db.add_all([ExportRecord(document_id=doc.id, actor_user_id=actor.id, format=format),
                UsageEvent(workspace_id=workspace, kind="export")])
    log_event(db, "export_downloaded", "document", request=request, workspace=workspace,
              actor=actor.id, target=doc.id, metadata={"format": format})
    db.commit()


@router.get("/api/documents/{id}/history")
def history(context=Depends(require_role("viewer", document=True)), db=Depends(get_db)):
    _, _, doc = context
    rows = db.scalars(select(AuditRecord).where(AuditRecord.document_id == doc.id)
                      .order_by(AuditRecord.created_at, AuditRecord.id))
    return {"filename": doc.filename, "expires_at": doc.expires_at, "status": doc.status,
            "versions": [row.summary for row in rows]}


@router.get("/api/workspaces/{workspace_id}/dashboard")
def dashboard(format: str = "json", context=Depends(require_role("owner")), db=Depends(get_db)):
    _, workspace, _ = context
    items = defaultdict(list)
    for audit, doc in db.execute(
        select(AuditRecord, Document).join(Document, Document.id == AuditRecord.document_id)
        .where(Document.workspace_id == workspace, Document.history_until > now())
        .order_by(AuditRecord.created_at, AuditRecord.id)
    ):
        items[doc].append(audit)
    issues = Counter()
    rows = []
    percentages = []
    for doc, versions in items.items():
        first, last = versions[0], versions[-1]
        open_findings = [item for item in last.findings if item["status"] != "verified_fixed"]
        issues.update(item["check_id"] for item in open_findings)
        before, after = first.summary["progress"], last.summary["progress"]
        if after["percent"] is not None:
            percentages.append(after["percent"])
        rows.append({
            "document_id": doc.id, "filename": doc.filename, "versions": len(versions),
            "before": f'{before["passed"]} of {before["evaluated"]}',
            "after": f'{after["passed"]} of {after["evaluated"]}',
            "open": len(open_findings), "verified": len(last.findings) - len(open_findings),
        })
    rows.sort(key=lambda row: (-row["open"], row["filename"].casefold()))
    if format == "csv":
        headers = ["filename", "versions", "before", "after", "open", "verified"]
        return csv_response("a11yra-dashboard.csv", headers, ([row[key] for key in headers] for row in rows))
    return {
        "documents": len(rows), "open": sum(row["open"] for row in rows),
        "verified": sum(row["verified"] for row in rows),
        "average_percent": round(sum(percentages) / len(percentages)) if percentages else None,
        "common_issues": [{"check": check, "count": count} for check, count in issues.most_common()],
        "attention": rows,
    }


class ShareInput(BaseModel):
    days: int = Field(default=7, ge=1, le=30)
    label: str = Field(default="", max_length=80)


@router.get("/api/documents/{id}/shares")
def shares(context=Depends(require_role("editor", document=True)), db=Depends(get_db)):
    _, _, doc = context
    return [{"id": row.id, "created_at": row.created_at, "expires_at": row.expires_at}
            for row in db.scalars(select(ReaderShare).where(
                ReaderShare.document_id == doc.id, ReaderShare.expires_at > now(),
            ).order_by(ReaderShare.created_at.desc()))]


@router.post("/api/documents/{id}/shares", status_code=201)
def publish(body: ShareInput, request: Request,
            context=Depends(require_role("editor", document=True, active=True)), db=Depends(get_db)):
    user, workspace, doc = context
    lock_workspace(db, workspace)
    db.refresh(doc)
    if doc.status != "active" or doc.expires_at <= now():
        raise document_not_found()
    plan = workspace_plan(db, workspace)
    if body.label and not plan.reader_branding:
        raise ApiError(403, "plan_branding", "Reader branding is available on the Institution plan.")
    if len(shares(context, db)) >= 5:
        raise ApiError(409, "share_limit", "Revoke an existing link before publishing another.")
    try:
        prepared = prepare_learner_download(request.app.state.documents, UUID(doc.id), True)
    except ExportPendingVerification:
        raise ApiError(409, "export_failed", "Run a new audit before publishing the reader.") from None
    except (OSError, ValueError, InvalidExport):
        raise ApiError(500, "export_failed", "The reader could not be prepared.") from None
    if prepared is None:
        raise document_not_found()
    raw = token()
    expires = min(now() + timedelta(days=body.days), doc.history_until)
    share = ReaderShare(document_id=doc.id, created_by=user.id, digest=digest(raw), expires_at=expires)
    db.add(share)
    db.flush()
    page = BeautifulSoup(prepared, "html.parser", from_encoding="utf-8")
    footer = page.new_tag("footer", attrs={"class": "header-inner"})
    updated = page.new_tag("p")
    updated.string = f"Last updated {share.created_at:%Y-%m-%d} UTC"
    footer.append(updated)
    if body.label:
        brand = page.new_tag("p")
        brand.string = body.label
        footer.append(brand)
    link = page.new_tag("a", href=f"mailto:{quote(user.email, safe='@')}", rel="noopener noreferrer")
    link.string = "Report a problem"
    footer.append(link)
    page.body.append(footer)
    path = share_path(request.app.state, share)
    try:
        path.write_bytes(str(page).encode("utf-8"))
        log_event(db, "reader_published", "share", request=request, workspace=workspace, actor=user.id, target=share.id)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"id": share.id, "url": f'{request.app.state.public_url}/r/{raw}', "expires_at": expires}


@router.delete("/api/documents/{id}/shares/{share_id}", status_code=204)
def revoke(share_id: UUID, request: Request,
           context=Depends(require_role("editor", document=True)), db=Depends(get_db)):
    user, workspace, doc = context
    item = db.get(ReaderShare, str(share_id))
    if not item or item.document_id != doc.id:
        raise document_not_found()
    revoke_share(db, request.app.state, item)
    log_event(db, "reader_revoked", "share", request=request, workspace=workspace, actor=user.id, target=item.id)
    db.commit()


@router.get("/r/{token}", include_in_schema=False)
def reader(token: str, request: Request, db=Depends(get_db)):
    headers = {
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Robots-Tag": "noindex, nofollow",
        "Cache-Control": "private, no-store",
    }
    if TOKEN_PATTERN.fullmatch(token):
        share = db.scalar(select(ReaderShare).where(ReaderShare.digest == digest(token), ReaderShare.expires_at > now()))
        if share:
            try:
                snapshot = share_path(request.app.state, share).read_bytes()
                headers["Content-Security-Policy"] = published_reader_policy(snapshot)
                return Response(snapshot, media_type="text/html", headers=headers)
            except FileNotFoundError:
                pass
    return Response("This reader link has expired or is no longer available.", status_code=404,
                    media_type="text/plain", headers=headers)
