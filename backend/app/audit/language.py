import re
from functools import cache

from docx.document import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import nsmap, qn

from app.audit._body import body_paragraphs, excerpt, visible_text
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


def _body_languages(document: Document, styles) -> dict[str, str]:
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

    languages: dict[str, str] = {}
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
            languages.setdefault(language, excerpt(visible_text(run), 65))
    return languages


def check_language(document: Document) -> tuple[Check, list[Finding]]:
    """Check the default w:val and compare it with the languages declared on body text."""
    try:
        styles = document.part.part_related_by(RT.STYLES).styles
    except KeyError:
        styles = None

    default_tag = _val(styles.element, DEFAULT_LANGUAGE_PATH) if styles is not None else None
    default_language = primary_language(default_tag)
    examples = _body_languages(document, styles)
    languages = set(examples)
    findings: list[Finding] = []
    result: CheckResult = "passed"
    summary = f"Default language in document properties: {default_tag}."

    if default_language is None:
        opening = next((text for paragraph in body_paragraphs(document)
                        if (text := excerpt(visible_text(paragraph), 65))), "")
        passage = f'the text beginning “{opening}”' if opening else "any untagged text in the document"
        result = "issues"
        summary = "Set the default document language."
        evidence = f"Default language: “{default_tag}” is unusable." if default_tag else "Default language: Not found."
        if opening:
            evidence += f' The first text reads “{opening}”.'
        suggested_language = next(iter(languages)) if len(languages) == 1 else None
        suggestion = (
            f'In Review fix, enter “{suggested_language}” if it matches the main text. This tag is already used in the document.'
            if suggested_language else
            f"Use {passage} to confirm the main language, then enter its tag in Review fix. For example, enter “en” for English."
        )
        findings.append(Finding(
            id="language-default-missing",
            check_id="language",
            location="Document default language",
            locator={"property": "default_language"},
            evidence=evidence,
            barrier=f"Without a default language, a screen reader may use its own pronunciation rules for {passage}.",
            suggestion=suggestion,
            severity="high",
            confidence="high",
            status="open",
            fixable="teacher_approved",
            suggested_value=suggested_language,
        ))
    else:
        languages.add(default_language)

    if len(languages) > 1:
        sample_tags = ", ".join(f'“{text}” ({tag})' for tag, text in sorted(examples.items()) if text)
        sample_context = f" Tagged text includes {sample_tags}." if sample_tags else ""
        if result == "passed":
            result = "needs_review"
            summary = f"Default language: {default_tag}. Review the other language tags in the text."
        else:
            summary = "Set the default language and review the language tags in the text."
        findings.append(Finding(
            id="language-mixed-review",
            check_id="language",
            location="Document default and main text",
            locator={"property": "body_language_tags"},
            evidence=f"Language tags include {', '.join(sorted(languages))}." + sample_context,
            barrier="A screen reader can switch pronunciation at the tagged text." + sample_context,
            suggestion=f"In Word, select passages tagged {', '.join(sorted(languages))} and use Review → Language → Set Proofing Language to correct any mismatches.",
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
