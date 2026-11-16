import re
from urllib.parse import unquote, urlsplit

from docx.document import Document
from docx.oxml.ns import qn

from app.audit._body import BODY_CONTENT, body_paragraphs, excerpt, visible_text
from app.models import Check, CheckResult, Finding

GENERIC_LABELS = {"click here", "here", "link", "read more"}


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


def _destination(document, link):
    relationship = document.part.rels.get(link.get(qn("r:id")))
    anchor = link.get(qn("w:anchor"))
    field = re.match(r'\s*HYPERLINK\s+(?:"([^"]+)"|(\S+))', link.get(qn("w:instr"), ""), re.I)
    target = relationship.target_ref if relationship else (field[1] or field[2]) if field else ""
    try:
        url = urlsplit(target)
        if url.hostname:
            topic = unquote(url.fragment or url.path.rstrip("/").rsplit("/", 1)[-1])
            topic = re.sub(r"[-_]+", " ", topic.removesuffix(".html"))
            suggestion = excerpt(topic.capitalize(), 80) if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9 ]{3,}", topic) and " " in topic else None
            return excerpt(url.hostname + url.path), suggestion
    except ValueError:
        pass
    return (f'bookmark “{excerpt(anchor)}”' if anchor else ""), None


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
            destination, replacement = _destination(document, link)
            context = excerpt(visible_text(paragraph))
            shown_label = excerpt(label)
            if kind == "url":
                shown_label = excerpt(label.split("?", 1)[0].split("#", 1)[0])
            evidence = f'Link {link_index + 1} in paragraph {paragraph_index + 1} is labeled “{shown_label}”.'
            if destination:
                evidence += f" It points to {destination}."
            if kind == "generic" and context != shown_label:
                evidence += f' The paragraph reads “{context}”.'
            barrier = (f'In a screen reader’s links list, “{shown_label}” gives readers no topic or action.'
                       if kind == "generic" else
                       f'A screen reader may read “{shown_label}” character by character, leaving readers to infer the topic.')
            suggestion = (f'Confirm the destination and replace “{shown_label}” with “{replacement}” if it describes the page.'
                          if replacement else
                          f'Replace “{shown_label}” with the name of the page or action'
                          f'{f" at {destination}" if destination else " described by this paragraph"}.')
            findings.append(Finding(
                id=f"link-{paragraph_index + 1:03d}-{link_index + 1:03d}",
                check_id="links",
                location=f"Link {link_index + 1}, paragraph {paragraph_index + 1}",
                locator={"paragraph_index": paragraph_index, "link_index": link_index},
                evidence=evidence,
                barrier=barrier,
                suggestion=suggestion,
                severity="medium" if kind == "generic" else "low",
                confidence="high",
                status="open",
                fixable="teacher_approved",
                suggested_value=replacement,
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
