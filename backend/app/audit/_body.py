from docx.document import Document
from docx.oxml.ns import nsmap, qn
from lxml.etree import XPath

# Audit the main story, including table cells, in document order.
BODY_CONTENT = "not(ancestor::w:txbxContent or ancestor::w:del or ancestor::w:moveFrom)"
_VISIBLE_TEXT_NODES = XPath(f".//w:t[{BODY_CONTENT}]", namespaces=nsmap)


def body_paragraphs(document: Document):
    return document.element.body.xpath(f".//w:p[{BODY_CONTENT}]")


def text_runs(paragraph):
    return paragraph.xpath(f".//w:r[w:t[normalize-space(.)] and {BODY_CONTENT}]")


def visible_text(element) -> str:
    return "".join(node.text or "" for node in visible_text_nodes(element))


def visible_text_nodes(element):
    return _VISIBLE_TEXT_NODES(element)


def word_value(element, path: str) -> str | None:
    child = element.find(path, namespaces=nsmap)
    return child.get(qn("w:val")) if child is not None else None


def word_flag(element, path: str) -> bool | None:
    child = element.find(path, namespaces=nsmap)
    if child is None:
        return None
    return child.get(qn("w:val"), "true") in {"true", "1", "on"}
