import re

from docx.document import Document
from docx.oxml.ns import qn

from app.audit._body import BODY_CONTENT, body_paragraphs, visible_text
from app.models import Check, CheckResult, Finding

GENERIC_LABELS = {"click here", "here", "link"}


def iter_link_elements(paragraph):
    elements = paragraph.xpath(f".//*[self::w:hyperlink or self::w:fldSimple][{BODY_CONTENT}]")
    for element in elements:
        if element.tag == qn("w:hyperlink") or re.match(
            r"\s*HYPERLINK(?:\s|$)", element.get(qn("w:instr"), ""), re.IGNORECASE
        ):
            yield element


def link_label_issue(label: str) -> str | None:
    normalized = " ".join(label.split()).strip(" .?!…:;()[]").casefold()
    if normalized in GENERIC_LABELS:
        return "generic"
    if re.fullmatch(r"(?:https?://|ftp://|www\.)\S+", normalized):
        return "url"
    return None


def check_links(document: Document) -> tuple[Check, list[Finding]]:
    findings: list[Finding] = []
    link_count = 0
    for paragraph_index, paragraph in enumerate(body_paragraphs(document)):
        for link_index, link in enumerate(iter_link_elements(paragraph)):
            link_count += 1
            label = visible_text(link)
            kind = link_label_issue(label)
            if kind is None:
                continue
            findings.append(Finding(
                id=f"link-{paragraph_index + 1:03d}-{link_index + 1:03d}",
                check_id="links",
                location=f"Link {link_index + 1}, paragraph {paragraph_index + 1}",
                locator={"paragraph_index": paragraph_index, "link_index": link_index},
                evidence=(
                    "The link uses a generic label such as “click here”."
                    if kind == "generic"
                    else "The link label is a web address."
                ),
                barrier="Readers who hear the link on its own may have trouble knowing where it goes.",
                suggestion="Use a short label that describes the destination or action.",
                severity="medium" if kind == "generic" else "low",
                confidence="high",
                status="open",
                fixable="teacher_approved",
            ))

    result: CheckResult
    if findings:
        result, summary = "issues", "Some links need clearer labels."
    elif link_count:
        result, summary = "passed", "No generic labels or web addresses found in the links checked."
    else:
        result, summary = "not_evaluated", "No supported links found in the main document."
    return Check(
        id="links", label="Link text", result=result, summary=summary,
        finding_ids=[finding.id for finding in findings],
    ), findings
