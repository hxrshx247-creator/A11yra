from pathlib import PurePath

from docx.document import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from app.audit._body import visible_text, word_value
from app.models import Check, Finding


PLACEHOLDER_TITLE = "give a sample title"


def _suggest_title(document: Document, filename: str) -> tuple[str | None, str]:
    for paragraph in document.paragraphs:
        text = " ".join(visible_text(paragraph._p).split())
        style = (word_value(paragraph._p, "w:pPr/w:pStyle") or "").lower()
        if style in {"title", "heading1"} and 0 < len(text) <= 255 and text.casefold() != PLACEHOLDER_TITLE:
            source = "the opening heading" if style == "heading1" else "the title in the document body"
            return text, source
        if text:
            break
    stem = " ".join(PurePath(filename).stem.replace("_", " ").split())
    if 0 < len(stem) <= 255 and stem.casefold() != PLACEHOLDER_TITLE:
        return stem, "the uploaded filename"
    return None, ""


def check_title(document: Document, filename: str = "") -> tuple[Check, list[Finding]]:
    """Check the title stored in the DOCX package's core properties."""
    try:
        core_part = document.part.package.part_related_by(RT.CORE_PROPERTIES)
        title = core_part.core_properties.title.strip()
    except KeyError:
        title = ""

    if title and title.casefold() != PLACEHOLDER_TITLE:
        return Check(
            id="title",
            label="Document title",
            result="passed",
            summary=f'Title in document properties: “{title}”',
            finding_ids=[],
        ), []

    suggested_title, source = _suggest_title(document, filename)
    if title:
        evidence = f'Title: “{title}” is placeholder text.'
        barrier = f'A screen reader or document list may identify this file as “{title}”, which gives readers no topic.'
    else:
        evidence = "Title: Not found in the document properties."
        file_label = f'its filename, “{filename}”' if filename else "its filename"
        barrier = f"A screen reader or document list may identify this file by {file_label} when the Title field is blank."
        if suggested_title and source != "the uploaded filename":
            barrier += f' Readers may miss the title shown in the body, “{suggested_title}”.'
    suggestion = "In Review fix, enter the main topic of this document in the Document title field."
    if suggested_title:
        suggestion = f'In Review fix, use “{suggested_title}” as the document title. This suggestion comes from {source}.'

    finding = Finding(
        id="title-missing",
        check_id="title",
        location="Document properties",
        locator={"property": "title"},
        evidence=evidence,
        barrier=barrier,
        suggestion=suggestion,
        severity="medium",
        confidence="high",
        status="open",
        fixable="teacher_approved",
        suggested_value=suggested_title,
    )
    return Check(
        id="title",
        label="Document title",
        result="issues",
        summary="Set a title that identifies this document.",
        finding_ids=[finding.id],
    ), [finding]
