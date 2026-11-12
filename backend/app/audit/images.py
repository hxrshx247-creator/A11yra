from docx.document import Document
from docx.oxml.ns import qn
import re

from app.audit._body import BODY_CONTENT, body_paragraphs
from app.models import Check, CheckResult, Finding

DECORATIVE_TAG = "{http://schemas.microsoft.com/office/drawing/2017/decorative}decorative"


def _is_decorative(properties) -> bool:
    return any(marker.get("val") in {"1", "true"} for marker in properties.iter(DECORATIVE_TAG))


def iter_picture_properties(document: Document):
    for paragraph_index, paragraph in enumerate(body_paragraphs(document)):
        drawings = paragraph.xpath(
            f".//w:drawing[{BODY_CONTENT}]/*[self::wp:inline or self::wp:anchor]"
            "[a:graphic/a:graphicData/pic:pic]"
        )
        for drawing in drawings:
            yield paragraph_index, drawing.find(qn("wp:docPr"))


def check_images(document: Document) -> tuple[Check, list[Finding]]:
    findings: list[Finding] = []
    image_count = 0
    for image_index, (paragraph_index, properties) in enumerate(iter_picture_properties(document)):
        image_count += 1
        description = properties.get("descr", "").strip() if properties is not None else ""
        if properties is not None and _is_decorative(properties):
            continue
        looks_like_filename = bool(description and re.fullmatch(r"[^\\/]+\.(?:png|jpe?g|gif|bmp|svg|tiff?)", description, re.IGNORECASE))
        if description and not looks_like_filename:
            continue

        findings.append(Finding(
            id=f"img-{image_index + 1:03d}",
            check_id="images",
            location=f"Image {image_index + 1}, paragraph {paragraph_index + 1}",
            locator={"image_index": image_index, "paragraph_index": paragraph_index},
            evidence=("The alt text looks like a filename, which may not describe the picture." if looks_like_filename
                      else "The image has no alt text and is unmarked as decorative."),
            barrier="A reader who cannot see the image may miss information it conveys.",
            suggestion="Review the image and edit its description, or mark it decorative if it adds no information.",
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
