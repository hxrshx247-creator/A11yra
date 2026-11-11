from docx.document import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from app.models import Check, Finding


def check_title(document: Document) -> tuple[Check, list[Finding]]:
    """Check the title stored in the DOCX package's core properties."""
    try:
        core_part = document.part.package.part_related_by(RT.CORE_PROPERTIES)
        title = core_part.core_properties.title.strip()
    except KeyError:
        title = ""

    if title:
        return Check(
            id="title",
            label="Document title",
            result="passed",
            summary="The document has a title in its file properties.",
            finding_ids=[],
        ), []

    finding = Finding(
        id="title-missing",
        check_id="title",
        location="Document properties",
        locator={"property": "title"},
        evidence="The Title field in the document properties is missing or blank.",
        barrier="Readers who use document metadata to identify an open file may have to rely on its filename.",
        suggestion="Enter a short title that describes this handout.",
        severity="medium",
        confidence="high",
        status="open",
        fixable="teacher_approved",
    )
    return Check(
        id="title",
        label="Document title",
        result="issues",
        summary="Add a title to the document properties.",
        finding_ids=[finding.id],
    ), [finding]
