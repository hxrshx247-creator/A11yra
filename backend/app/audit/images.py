from docx.document import Document
from docx.oxml.ns import qn

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
        if properties is not None and (properties.get("descr", "").strip() or _is_decorative(properties)):
            continue

        findings.append(Finding(
            id=f"img-{image_index + 1:03d}",
            check_id="images",
            location=f"Image {image_index + 1}, paragraph {paragraph_index + 1}",
            locator={"image_index": image_index, "paragraph_index": paragraph_index},
            evidence="The image has no alt text and is unmarked as decorative.",
            barrier="A reader who cannot see the image may miss information it conveys.",
            suggestion="Describe what the image communicates, or mark it decorative if it adds no information.",
            severity="medium",
            confidence="high",
            status="open",
            fixable="teacher_approved",
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
