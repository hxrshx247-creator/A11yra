import re
from functools import cache

from docx.document import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import nsmap, qn

from app.models import Check, CheckResult, Finding

DEFAULT_LANGUAGE_PATH = "w:docDefaults/w:rPrDefault/w:rPr/w:lang"


def _val(element, path: str) -> str | None:
    child = element.find(path, namespaces=nsmap)
    if child is None:
        return None
    return child.get(qn("w:val"), "").strip() or None


def primary_language(tag: str | None) -> str | None:
    if tag is None or re.fullmatch(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*", tag, re.IGNORECASE) is None:
        return None
    primary = tag.split("-", 1)[0].lower()
    return None if primary in {"mul", "und", "zxx"} else primary


def _body_languages(document: Document, styles) -> set[str]:
    @cache
    def style_language(style_id: str | None, style_type: WD_STYLE_TYPE) -> str | None:
        style = styles.get_by_id(style_id, style_type) if styles is not None else None
        visited = set()
        while style is not None and style.style_id not in visited:
            visited.add(style.style_id)
            language = _val(style.element, "w:rPr/w:lang")
            if language is not None:
                return language
            style = style.base_style
        return None

    languages: set[str] = set()
    # Word uses these run elements for ordinary text, including text inside tables and links.
    for run in document.element.body.xpath(".//w:p//w:r[w:t[normalize-space(.)]]"):
        paragraph = run.xpath("ancestor::w:p[1]")[0]
        tag = (
            _val(run, "w:rPr/w:lang")
            or style_language(_val(run, "w:rPr/w:rStyle"), WD_STYLE_TYPE.CHARACTER)
            or style_language(_val(paragraph, "w:pPr/w:pStyle"), WD_STYLE_TYPE.PARAGRAPH)
        )
        language = primary_language(tag)
        if language is not None:
            languages.add(language)
    return languages


def check_language(document: Document) -> tuple[Check, list[Finding]]:
    """Check the default w:val and compare it with the languages declared on body text."""
    try:
        styles = document.part.part_related_by(RT.STYLES).styles
    except KeyError:
        styles = None

    default_tag = _val(styles.element, DEFAULT_LANGUAGE_PATH) if styles is not None else None
    default_language = primary_language(default_tag)
    languages = _body_languages(document, styles)
    findings: list[Finding] = []
    result: CheckResult = "passed"
    summary = "The document has a default language."

    if default_language is None:
        result = "issues"
        summary = "Set the default document language."
        findings.append(Finding(
            id="language-default-missing",
            check_id="language",
            location="Document default language",
            locator={"property": "default_language"},
            evidence="The default run properties have no usable primary language tag.",
            barrier="Without a document language, a screen reader may use the wrong pronunciation rules.",
            suggestion="Choose the language used for most of the document.",
            severity="high",
            confidence="high",
            status="open",
            fixable="teacher_approved",
        ))
    else:
        languages.add(default_language)

    if len(languages) > 1:
        if result == "passed":
            result = "needs_review"
            summary = "Review the languages marked in the document."
        else:
            summary = "Set the default language and review the language tags in the text."
        findings.append(Finding(
            id="language-mixed-review",
            check_id="language",
            location="Document default and main text",
            locator={"property": "body_language_tags"},
            evidence=f"Language tags indicate more than one language ({', '.join(sorted(languages))}).",
            barrier="Screen readers can pronounce passages incorrectly if their language tags are wrong.",
            suggestion="Check that each passage is tagged with the language it uses.",
            severity="medium",
            confidence="medium",
            status="needs_review",
            fixable="recommendation_only",
        ))

    return Check(
        id="language",
        label="Document language",
        result=result,
        summary=summary,
        finding_ids=[finding.id for finding in findings],
    ), findings
