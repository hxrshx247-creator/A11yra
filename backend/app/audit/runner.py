from datetime import datetime, timezone
from uuid import UUID, uuid4

from docx.document import Document

from app.audit.headings import check_headings
from app.audit.images import check_images
from app.audit.language import check_language
from app.audit.links import check_links
from app.audit.score import calculate_progress
from app.audit.tables import check_tables
from app.audit.title import check_title
from app.models import Audit, Check, Finding

CHECKS = (check_title, check_language, check_headings, check_images, check_tables, check_links)


def run_audit(document: Document, document_id: UUID) -> Audit:
    checks: list[Check] = []
    findings: list[Finding] = []
    for run_check in CHECKS:
        check, check_findings = run_check(document)
        checks.append(check)
        findings.extend(check_findings)

    return Audit(
        audit_id=uuid4(),
        document_id=document_id,
        created_at=datetime.now(timezone.utc),
        checks=checks,
        findings=findings,
        progress=calculate_progress(checks),
    )
