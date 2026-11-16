import re
from functools import cache

from docx.document import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import nsmap

from app.audit._body import body_paragraphs, excerpt, text_runs, visible_text, word_flag, word_value
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
    if len(text) >= 80 or len(text.split()) > 12 or text.endswith((".", "?", "!", "…")):
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
    previous_heading = ""
    text_paragraphs = 0
    for index, paragraph in enumerate(body_paragraphs(document)):
        runs = text_runs(paragraph)
        if not runs:
            continue
        text = visible_text(paragraph).strip()
        label = excerpt(text)
        text_paragraphs += 1
        chain = paragraph_styles(word_value(paragraph, "w:pPr/w:pStyle"))
        level = _heading_level(chain)
        location = f"Paragraph {index + 1}"
        if level is not None:
            if level > previous_level + 1:
                evidence = (
                    f'“{label}” is Heading {level} after “{previous_heading}” (Heading {previous_level}).'
                    if previous_level
                    else f'The first heading, “{label}”, is Heading {level}.'
                )
                findings.append(Finding(
                    id=f"heading-skip-{index + 1:03d}", check_id="headings", location=location,
                    locator={"paragraph_index": index}, evidence=evidence,
                    barrier=f'“{label}” appears deeper in heading navigation than the preceding outline establishes.',
                    suggestion=f'Convert “{label}” to Heading {previous_level + 1} if it belongs at the next level of this outline.',
                    severity="medium", confidence="high", status="open", fixable="teacher_approved",
                    preview=text,
                    suggested_value=str(previous_level + 1),
                ))
            previous_level = level
            previous_heading = label
        elif _looks_like_heading(paragraph, runs, chain, body_size):
            findings.append(Finding(
                id=f"heading-lookalike-{index + 1:03d}", check_id="headings", location=location,
                locator={"paragraph_index": index},
                evidence=f'“{label}” looks like a heading because of its size or bold text, but uses no heading level.',
                barrier=f'Readers who navigate by headings will skip “{label}” if it is meant to start a section.',
                suggestion=f'If “{label}” starts a section, convert it to Heading {min(previous_level + 1, 6)}. Otherwise select Not a heading.',
                severity="low", confidence="high", status="needs_review", fixable="teacher_approved",
                preview=text,
                suggested_value=str(min(previous_level + 1, 6)),
            ))

    if text_paragraphs and not previous_level:
        candidate = next((finding.preview for finding in findings if finding.preview), None)
        starting_point = f' Start by reviewing “{excerpt(candidate)}”.' if candidate else ""
        findings.insert(0, Finding(
            id="headings-missing", check_id="headings", location="Main document",
            locator={"property": "heading_structure"},
            evidence=f"None of the {text_paragraphs} text paragraphs use a heading style.{starting_point}",
            barrier=f"Heading navigation offers no stops in these {text_paragraphs} paragraphs.",
            suggestion="In Word, apply Heading 1 to the main section titles and Heading 2 to their subsections." + starting_point,
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
