from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.audit._body import body_paragraphs
from app.audit.images import iter_picture_drawings
from app.audit.links import iter_link_elements
from app.audit.tables import body_tables, table_rows
from app.models import Finding


def flag_label(finding: Finding) -> str:
    return {"title": "Document title", "language": "Document language"}.get(finding.check_id, finding.location)


def insert_preview_flags(document, findings: list[Finding], prefix: str) -> None:
    """Add temporary bookmarks at audit locations in the preview copy."""
    paragraphs = body_paragraphs(document)
    images = list(iter_picture_drawings(document))
    tables = body_tables(document)
    next_id = max((int(value) for value in document.element.xpath(".//w:bookmarkStart/@w:id")
                   if value.isascii() and value.isdecimal() and len(value) < 10), default=0) + 1

    def item(values, index):
        return values[index] if isinstance(index, int) and 0 <= index < len(values) else None

    for index, finding in enumerate(findings):
        locator = finding.locator
        paragraph = item(paragraphs, locator.get("paragraph_index"))
        target = None
        if finding.check_id == "images":
            image = item(images, locator.get("image_index"))
            if image is not None:
                drawing = image[1]
                target = next(iter(drawing.xpath("ancestor::w:r[1]")), None)
        elif finding.check_id == "links" and paragraph is not None:
            target = item(list(iter_link_elements(paragraph)), locator.get("link_index"))
        elif finding.check_id == "tables":
            table = item(tables, locator.get("table_index"))
            rows = table_rows(table) if table is not None else []
            if rows:
                paragraph = next(iter(rows[0].xpath("./w:tc[1]/w:p[1]")), None)
        elif finding.check_id != "headings":
            continue

        if paragraph is None:
            continue
        while target is not None and target.getparent() is not paragraph:
            target = target.getparent()
        start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
        start.set(qn("w:name"), f"{prefix}-{index}")
        for element in (start, end):
            element.set(qn("w:id"), str(next_id))
            if target is None:
                paragraph.append(element)
            else:
                target.addprevious(element)
        next_id += 1


def render_preview_flags(page, findings: list[Finding], prefix: str) -> None:
    for link in page.article.find_all("a", href=True):
        if not link["href"].startswith("#"):
            del link["href"]
    for index, finding in enumerate(findings):
        bookmark = page.article.find(id=f"docx-{prefix}-{index}")
        flag = page.new_tag("mark", id=f"finding-{finding.id}", tabindex="-1")
        flag.string = f"⚑ {flag_label(finding)}"
        if bookmark is not None:
            bookmark.replace_with(flag)
            flag.insert_before(" ")
            flag.insert_after(" ")
        else:
            entry = page.new_tag("p")
            entry.append(flag)
            page.header.append(entry)
