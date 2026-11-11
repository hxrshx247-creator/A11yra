import re
from functools import cache

from docx.document import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import nsmap

from app.audit._body import body_paragraphs, text_runs, visible_text, word_flag, word_value
from app.models import Check, CheckResult, Finding


def _style_chain(style):
    seen = set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        yield style
        style = style.base_style


def _heading_level(style_chain) -> int | None:
    for style in style_chain:
        outline = word_value(style.element, "w:pPr/w:outlineLvl")
        if outline is not None and len(outline) == 1 and outline in "0123456789":
            return int(outline) + 1 if outline != "9" else None
        # Built-in names are usually stored in English even in localized Word.
        for name in (style.name or "", style.style_id):
            match = re.fullmatch(r"heading ?([1-9])", name, re.IGNORECASE)
            if match is not None:
                return int(match[1])
    return None


def _first_defined(values):
    return next((value for value in values if value is not None), None)


def _looks_like_heading(paragraph, runs, styles, body_size: int) -> bool:
    if paragraph.xpath("ancestor::w:tc"):
        return False
    if any(
        (style.name or "").lower().startswith(("title", "subtitle", "caption", "list"))
        or style.element.find("w:pPr/w:numPr", namespaces=nsmap) is not None
        for style in styles
    ) or paragraph.find("w:pPr/w:numPr", namespaces=nsmap) is not None:
        return False

    text = visible_text(paragraph).strip()
    if len(text) > 90 or len(text.split()) > 12 or text.endswith((".", "?", "!", "…")):
        return False

    style_bold = _first_defined(word_flag(style.element, "w:rPr/w:b") for style in styles)
    style_size = _first_defined(word_value(style.element, "w:rPr/w:sz") for style in styles)
    bold = [_first_defined((word_flag(run, "w:rPr/w:b"), style_bold)) for run in runs]
    sizes = [_half_points(word_value(run, "w:rPr/w:sz") or style_size) for run in runs]
    # Word stores font sizes in half-points. Compare the whole line with body text.
    large_at = max(28, body_size + 8)
    return all(bold) or all(size >= large_at for size in sizes)


def _half_points(value: str | None) -> int:
    return int(value) if value and len(value) <= 4 and value.isascii() and value.isdigit() else 0


def check_headings(document: Document) -> tuple[Check, list[Finding]]:
    try:
        styles = document.part.part_related_by(RT.STYLES).styles
    except KeyError:
        styles = None

    @cache
    def paragraph_styles(style_id: str | None):
        style = styles.get_by_id(style_id, WD_STYLE_TYPE.PARAGRAPH) if styles is not None else None
        return tuple(_style_chain(style))

    normal_size = _first_defined(
        word_value(style.element, "w:rPr/w:sz") for style in paragraph_styles(None)
    )
    if normal_size is None and styles is not None:
        normal_size = word_value(styles.element, "w:docDefaults/w:rPrDefault/w:rPr/w:sz")
    body_size = _half_points(normal_size) or 22

    findings: list[Finding] = []
    previous_level = 0
    text_paragraphs = 0
    for index, paragraph in enumerate(body_paragraphs(document)):
        runs = text_runs(paragraph)
        if not runs:
            continue
        text_paragraphs += 1
        chain = paragraph_styles(word_value(paragraph, "w:pPr/w:pStyle"))
        level = _heading_level(chain)
        location = f"Paragraph {index + 1}"
        if level is not None:
            if level > previous_level + 1:
                evidence = (
                    f"Heading {level} follows Heading {previous_level}."
                    if previous_level
                    else f"The first heading is Heading {level}."
                )
                findings.append(Finding(
                    id=f"heading-skip-{index + 1:03d}", check_id="headings", location=location,
                    locator={"paragraph_index": index}, evidence=evidence,
                    barrier="A skipped level can make the document outline harder to follow.",
                    suggestion=f"Use Heading {previous_level + 1} in Word if this starts the next section level.",
                    severity="medium", confidence="high", status="open", fixable="recommendation_only",
                ))
            previous_level = level
        elif _looks_like_heading(paragraph, runs, chain, body_size):
            findings.append(Finding(
                id=f"heading-lookalike-{index + 1:03d}", check_id="headings", location=location,
                locator={"paragraph_index": index},
                evidence="A short paragraph is bold or larger than the body text.",
                barrier="A section label formatted this way may be missing from screen-reader heading navigation.",
                suggestion="If this starts a section, apply the appropriate Heading style in Word.",
                severity="low", confidence="medium", status="needs_review", fixable="recommendation_only",
            ))

    if text_paragraphs and not previous_level:
        findings.insert(0, Finding(
            id="headings-missing", check_id="headings", location="Main document",
            locator={"property": "heading_structure"},
            evidence="No paragraphs with text use a heading style.",
            barrier="Readers cannot jump between sections using heading navigation.",
            suggestion="Apply Heading styles to the section titles in Word.",
            severity="medium" if text_paragraphs >= 10 else "low",
            confidence="high", status="open", fixable="recommendation_only",
        ))

    result: CheckResult
    if not text_paragraphs:
        result, summary = "not_evaluated", "No text paragraphs to check."
    elif any(finding.status == "open" for finding in findings):
        result, summary = "issues", "Review the document’s heading structure."
    elif findings:
        result, summary = "needs_review", "Some paragraphs look like possible section headings."
    else:
        result, summary = "passed", "Heading styles form a continuous outline."
    return Check(
        id="headings", label="Heading structure", result=result, summary=summary,
        finding_ids=[finding.id for finding in findings],
    ), findings
