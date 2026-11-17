from docx.document import Document
from docx.oxml.ns import qn
import re

from app.audit._body import BODY_CONTENT, body_paragraphs, excerpt, visible_text
from app.models import Check, CheckResult, Finding

DECORATIVE_TAG = "{http://schemas.microsoft.com/office/drawing/2017/decorative}decorative"


def _is_decorative(properties) -> bool:
    return any(marker.get("val") in {"1", "true"} for marker in properties.iter(DECORATIVE_TAG))


def iter_picture_drawings(document: Document):
    """Yield each picture drawing with its paragraph index."""
    for paragraph_index, paragraph in enumerate(body_paragraphs(document)):
        drawings = paragraph.xpath(
            f".//w:drawing[{BODY_CONTENT}]/*[self::wp:inline or self::wp:anchor]"
            "[a:graphic/a:graphicData/pic:pic]"
        )
        for drawing in drawings:
            yield paragraph_index, drawing


def iter_picture_properties(document: Document):
    """Yield each picture's paragraph index and drawing properties."""
    for paragraph_index, drawing in iter_picture_drawings(document):
        yield paragraph_index, drawing.find(qn("wp:docPr"))


def check_images(document: Document) -> tuple[Check, list[Finding]]:
    """Check pictures for descriptions or decorative marking."""
    findings: list[Finding] = []
    image_count = 0
    paragraphs = body_paragraphs(document)
    for image_index, (paragraph_index, properties) in enumerate(iter_picture_properties(document)):
        image_count += 1
        description = properties.get("descr", "").strip() if properties is not None else ""
        if properties is not None and _is_decorative(properties):
            continue
        looks_like_filename = bool(description and re.fullmatch(r"[^\\/]+\.(?:png|jpe?g|gif|bmp|svg|tiff?)", description, re.IGNORECASE))
        if description and not looks_like_filename:
            continue

        paragraph = paragraphs[paragraph_index]
        caption = paragraph.xpath("following-sibling::*[1][self::w:p]")
        nearby = excerpt(visible_text(caption[0])) if caption else ""
        if not re.match(r"(?:fig(?:ure)?\.?|image|diagram|chart)\s+\d", nearby, re.I):
            nearby = ""
        name = f"Image {image_index + 1}"
        context = f' The next paragraph reads “{nearby}”.' if nearby else ""
        evidence = (f'{name} uses “{excerpt(description)}” as alt text, which looks like a filename.'
                    if looks_like_filename else f"{name} in paragraph {paragraph_index + 1} has no alt text.")
        barrier = (f'Readers hear the caption “{nearby}” and may miss the visual details it refers to.'
                   if nearby else f'A screen reader may announce {name.lower()} without telling the reader what it shows.'
                   if not description else f'A screen reader may announce “{excerpt(description)}” without explaining the picture.')
        suggestion = (f'Inspect {name.lower()} beside “{nearby}” in the flagged preview. Describe the visual information the caption leaves out.'
                      if nearby else f'Inspect the flagged {name.lower()} and describe its main subject or message in Alt text.')
        if not nearby:
            suggestion += " Choose Decorative if the picture adds no information."
        findings.append(Finding(
            id=f"img-{image_index + 1:03d}",
            check_id="images",
            location=f"Image {image_index + 1}, paragraph {paragraph_index + 1}",
            locator={"image_index": image_index, "paragraph_index": paragraph_index},
            evidence=evidence + context,
            barrier=barrier,
            suggestion=suggestion,
            severity="medium",
            confidence="high",
            status="needs_review" if looks_like_filename else "open",
            fixable="teacher_approved",
            preview=description or None,
        ))

    result: CheckResult
    if findings:
        result, summary = "issues", "Some images need alt text or a decorative decision."
    elif image_count:
        result, summary = "passed", "The pictures checked have descriptions or are marked decorative."
    else:
        result, summary = "not_evaluated", "No supported pictures found in the main document."
    return Check(
        id="images", label="Image alt text", result=result, summary=summary,
        finding_ids=[finding.id for finding in findings],
    ), findings
