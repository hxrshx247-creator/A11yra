from io import BytesIO
from uuid import UUID

from docx import Document
from docx.document import Document as WordDocument

from app.core.storage import DocumentStore
from app.models import AppliedFix, Audit, Fix, FixResponse, SkippedFix
from app.repair.operations import (
    RepairRejected,
    set_alt_text,
    set_language,
    set_link_text,
    set_table_header,
    set_heading,
    set_title,
)

REPAIRS = {
    "set_title": ("title", {"title"}, set_title),
    "set_language": ("language", {"lang"}, set_language),
    "set_alt_text": ("images", {"alt_text", "decorative"}, set_alt_text),
    "set_link_text": ("links", {"new_text"}, set_link_text),
    "set_table_header": ("tables", set(), set_table_header),
    "set_heading": ("headings", {"heading_level"}, set_heading),
}


def apply_fixes(document: WordDocument, audit: Audit, fixes: list[Fix]) -> FixResponse:
    findings = {finding.id: finding for finding in audit.findings}
    result = FixResponse(applied=[], skipped=[])
    for fix in fixes:
        finding = findings.get(fix.finding_id)
        check_id, fields, repair = REPAIRS[fix.type]
        try:
            if finding is None:
                raise RepairRejected("This finding could not be found in the saved audit.")
            if finding.fixable != "teacher_approved":
                raise RepairRejected("This finding is a recommendation to review in Word.")
            if finding.status not in {"open", "needs_review"}:
                raise RepairRejected("This finding is no longer open for a fix.")
            if finding.check_id != check_id:
                raise RepairRejected("This repair type does not match the finding.")
            if fix.payload.model_fields_set - fields:
                raise RepairRejected("The request includes fields for a different repair type.")
            repair(document, finding, fix.payload)
        except RepairRejected as error:
            result.skipped.append(SkippedFix(finding_id=fix.finding_id, reason=str(error)))
        else:
            finding.status = "fixed_unverified"
            result.applied.append(AppliedFix(finding_id=fix.finding_id, status="fixed_unverified"))
    return result


def repair_document(store: DocumentStore, document_id: UUID, fixes: list[Fix]) -> FixResponse | None:
    with store.locked_session(document_id) as session:
        if session is None:
            return None
        state = store.current_state(session)
        audit = store.read_audit(state)
        document = Document(state / "working.docx")
        result = apply_fixes(document, audit, fixes)
        if result.applied:
            output = BytesIO()
            document.save(output)
            store.commit_state(session, state, output.getvalue(), audit)
        return result
