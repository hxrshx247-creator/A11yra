import re
from itertools import islice

from docx.document import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml.etree import SubElement

from app.audit._body import body_paragraphs, visible_text_nodes
from app.audit.images import DECORATIVE_TAG, iter_picture_properties
from app.audit.language import primary_language
from app.audit.links import iter_link_elements, link_label_issue
from app.audit.tables import body_tables, table_rows
from app.models import Finding, FixPayload

DECORATIVE_EXTENSION = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"
INVALID_XML_TEXT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


class RepairRejected(Exception):
    """A repair could not be applied. The message is safe to show to the teacher."""


def _required_text(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if not text or INVALID_XML_TEXT.search(text):
        raise RepairRejected(f"Enter valid {label} text.")
    return text


def _index(finding: Finding, key: str) -> int:
    index = finding.locator.get(key)
    if not isinstance(index, int) or index < 0:
        raise RepairRejected("The saved finding does not point to a valid document location.")
    return index


def _child(parent, tag: str, *, first: bool = False):
    child = parent.find(qn(tag))
    if child is None:
        child = OxmlElement(tag)
        if first:
            parent.insert(0, child)
        else:
            parent.append(child)
    return child


def set_title(document: Document, _finding: Finding, payload: FixPayload) -> None:
    """Set the document title in its core properties."""
    title = _required_text(payload.title, "title")
    if len(title) > 255:
        raise RepairRejected("Use a document title of 255 characters or fewer.")
    document.core_properties.title = title


def set_language(document: Document, _finding: Finding, payload: FixPayload) -> None:
    """Set the default proofing language for the document."""
    language = (payload.lang or "").strip()
    if primary_language(language) is None:
        raise RepairRejected("Choose a language tag such as en, en-IN, or hi.")

    defaults = _child(document.styles.element, "w:docDefaults", first=True)
    default_run = _child(defaults, "w:rPrDefault", first=True)
    properties = _child(default_run, "w:rPr")
    tag = properties.find(qn("w:lang"))
    if tag is None:
        tag = OxmlElement("w:lang")
        properties.insert_element_before(tag, "w:eastAsianLayout", "w:specVanish", "w:oMath", "w:rPrChange")
    tag.set(qn("w:val"), language)


def set_alt_text(document: Document, finding: Finding, payload: FixPayload) -> None:
    """Set the selected picture's alt text or mark it decorative."""
    if payload.decorative and (payload.alt_text or "").strip():
        raise RepairRejected("Choose decorative or provide alt text.")
    description = None if payload.decorative else _required_text(payload.alt_text, "alt")
    index = _index(finding, "image_index")
    picture = next(islice(iter_picture_properties(document), index, index + 1), None)
    if picture is None or picture[1] is None:
        raise RepairRejected("The picture’s properties could not be found.")

    _, properties = picture
    markers = list(properties.iter(DECORATIVE_TAG))
    if description is not None:
        properties.set("descr", description)
        for marker in markers:
            marker.set("val", "0")
        return

    if not markers:
        extensions = _child(properties, "a:extLst")
        extension = SubElement(extensions, qn("a:ext"), uri=DECORATIVE_EXTENSION)
        namespace = DECORATIVE_TAG.split("}")[0][1:]
        markers.append(SubElement(extension, DECORATIVE_TAG, nsmap={"adec": namespace}))
    for marker in markers:
        marker.set("val", "1")
    properties.attrib.pop("descr", None)


def set_link_text(document: Document, finding: Finding, payload: FixPayload) -> None:
    """Replace the selected link's visible label while keeping its destination."""
    label = _required_text(payload.new_text, "link label")
    if link_label_issue(label) is not None:
        raise RepairRejected("Use a label that describes where the link goes.")

    paragraphs = body_paragraphs(document)
    paragraph_index = _index(finding, "paragraph_index")
    if paragraph_index >= len(paragraphs):
        raise RepairRejected("The link’s paragraph could not be found.")
    index = _index(finding, "link_index")
    link = next(islice(iter_link_elements(paragraphs[paragraph_index]), index, index + 1), None)
    nodes = visible_text_nodes(link) if link is not None else []
    if not nodes:
        raise RepairRejected("The link text could not be found.")

    # Retain the link and its destination. Reuse the first text node's formatting.
    nodes[0].text = label
    for node in nodes[1:]:
        node.text = ""


def set_table_header(document: Document, finding: Finding, _payload: FixPayload) -> None:
    """Mark the first row of the selected table as a header."""
    tables = body_tables(document)
    index = _index(finding, "table_index")
    rows = table_rows(tables[index]) if index < len(tables) else []
    if not rows:
        raise RepairRejected("The table’s first row could not be found.")

    properties = rows[0].get_or_add_trPr()
    marker = properties.find(qn("w:tblHeader"))
    if marker is None:
        marker = OxmlElement("w:tblHeader")
        properties.insert_element_before(
            marker, "w:tblCellSpacing", "w:jc", "w:hidden", "w:ins", "w:del", "w:trPrChange"
        )
    marker.set(qn("w:val"), "1")


def set_heading(document: Document, finding: Finding, payload: FixPayload) -> None:
    """Apply the selected heading level to the target paragraph."""
    level = payload.heading_level
    if level is None or not 1 <= level <= 6:
        raise RepairRejected("Choose a heading level from 1 to 6.")
    paragraphs = body_paragraphs(document)
    index = _index(finding, "paragraph_index")
    if index >= len(paragraphs):
        raise RepairRejected("The paragraph could not be found.")
    # Assigning a real built-in style updates the Word outline while retaining direct run formatting.
    target = paragraphs[index]
    ppr = target.get_or_add_pPr()
    style = ppr.find(qn("w:pStyle"))
    if style is None:
        style = OxmlElement("w:pStyle")
        ppr.insert(0, style)
    style.set(qn("w:val"), document.styles[f"Heading {level}"].style_id)
