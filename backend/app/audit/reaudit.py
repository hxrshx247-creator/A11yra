from collections import defaultdict
from io import BytesIO
from uuid import UUID

from docx import Document

from app.audit.runner import run_audit
from app.audit.score import calculate_progress
from app.core.storage import DocumentStore
from app.models import Audit, AuditDiff, CheckId, Finding, ReauditResponse


def compare_audits(previous: Audit, fresh: Audit) -> AuditDiff:
    old_by_id = {finding.id: finding for finding in previous.findings}
    fresh_ids = {finding.id for finding in fresh.findings}
    evaluated = {check.id for check in fresh.checks if check.result != "not_evaluated"}
    verified: list[str] = []
    new = [
        finding.id
        for finding in fresh.findings
        if finding.id not in old_by_id or old_by_id[finding.id].status == "verified_fixed"
    ]

    for finding in previous.findings:
        if finding.id in fresh_ids:
            continue
        if finding.status == "fixed_unverified" and finding.check_id in evaluated:
            finding = finding.model_copy(update={"status": "verified_fixed"})
            verified.append(finding.id)
        fresh.findings.append(finding)

    grouped: dict[CheckId, list[Finding]] = defaultdict(list)
    for finding in fresh.findings:
        grouped[finding.check_id].append(finding)

    for check in fresh.checks:
        findings = grouped[check.id]
        check.finding_ids = [finding.id for finding in findings]
        if check.result == "passed" and any(finding.status != "verified_fixed" for finding in findings):
            check.result = "needs_review"
            check.summary = "A finding from the previous audit still needs review."

    fresh.progress = calculate_progress(fresh.checks)
    return AuditDiff(
        verified_fixed=verified,
        still_open=[finding.id for finding in fresh.findings if finding.status == "open" and finding.id not in new],
        new_findings=new,
        needs_review=[
            finding.id for finding in fresh.findings if finding.status in {"needs_review", "fixed_unverified"}
        ],
        progress_before=previous.progress,
        progress_after=fresh.progress,
    )


def reaudit_document(store: DocumentStore, document_id: UUID) -> ReauditResponse | None:
    with store.locked_session(document_id) as session:
        if session is None:
            return None
        state = store.current_state(session)
        previous = store.read_audit(state)
        contents = (state / "working.docx").read_bytes()
        audit = run_audit(Document(BytesIO(contents)), document_id)
        diff = compare_audits(previous, audit)
        store.commit_state(session, state, contents, audit)
        return ReauditResponse(audit=audit, diff=diff)
