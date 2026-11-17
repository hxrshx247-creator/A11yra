import re

from docx.document import Document as WordDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.enum.style import WD_STYLE_TYPE

from app.audit._body import body_paragraphs, visible_text, word_flag, word_value
from app.audit.headings import _heading_level, _style_chain
from app.audit.images import DECORATIVE_TAG, iter_picture_properties
from app.audit.language import DEFAULT_LANGUAGE_PATH, primary_language
from app.audit.links import iter_link_elements, link_label_issue
from app.audit.tables import body_tables, table_rows
from app.audit.title import PLACEHOLDER_TITLE
from app.models import Audit, ReaderItem, ReaderPreview


def _blocks(parent):
    """Yield Word paragraphs and tables in the same body order used by audits."""
    for child in parent.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _language(document: WordDocument) -> str | None:
    try:
        styles = document.part.part_related_by(RT.STYLES).styles
        return word_value(styles.element, DEFAULT_LANGUAGE_PATH)
    except KeyError:
        return None


def build_reader_preview(document: WordDocument, audit: Audit, version: str) -> ReaderPreview:
    """Build a linear preview of the document with audit findings in context."""
    findings = audit.findings
    title = document.core_properties.title.strip()
    placeholder = title.casefold() == PLACEHOLDER_TITLE
    items = [ReaderItem(type="title", text=f"Document title: {title or 'none (file name will be read instead)'}",
                        issue="needs_review" if placeholder else "missing" if not title else None,
                        finding_id="title-missing" if placeholder or not title else None)]
    lang = _language(document)
    usable_lang = primary_language(lang)
    items.append(ReaderItem(type="language", text=f"Language: {lang or 'not set'}",
                            issue="missing" if not usable_lang else None,
                            finding_id="language-default-missing" if not usable_lang else None))

    paragraph_numbers = {element: index for index, element in enumerate(body_paragraphs(document), 1)}
    table_numbers = {element: index for index, element in enumerate(body_tables(document), 1)}
    pictures_by_paragraph = {}
    for image_index, (paragraph_index, properties) in enumerate(iter_picture_properties(document), 1):
        pictures_by_paragraph.setdefault(paragraph_index + 1, []).append((image_index, properties))
    for block in _blocks(document):
        if isinstance(block, Paragraph):
            para_index = paragraph_numbers[block._p]
            text = visible_text(block._p).strip()
            for image_index, props in pictures_by_paragraph.get(para_index, ()):
                alt = props.get("descr", "").strip() if props is not None else ""
                decorative = props is not None and any(
                    marker.get("val") in {"1", "true"} for marker in props.iter(DECORATIVE_TAG)
                )
                fid = f"img-{image_index:03d}"
                image_issue = not decorative and (not alt or bool(
                    re.fullmatch(r"[^\\/]+\.(?:png|jpe?g|gif|bmp|svg|tiff?)", alt, re.IGNORECASE)
                ))
                items.append(ReaderItem(type="image", text=("Image: decorative, skipped" if decorative else
                                   f"Image: {alt}" if alt else "Image: no description"),
                                   issue="needs_review" if image_issue and alt else "missing" if image_issue else None,
                                   finding_id=fid if image_issue and not decorative else None))
            if text:
                style_id = word_value(block._p, "w:pPr/w:pStyle")
                styles = block.part.part_related_by(RT.STYLES).styles
                style = styles.get_by_id(style_id, WD_STYLE_TYPE.PARAGRAPH) if style_id else None
                level = _heading_level(_style_chain(style)) if style else None
                paragraph_finding = next((finding for finding in findings
                    if finding.check_id == "headings" and finding.locator.get("paragraph_index") == para_index - 1
                    and finding.status != "dismissed"
                    and (version == "original" or finding.status not in {"fixed_unverified", "verified_fixed"})), None)
                if level:
                    items.append(ReaderItem(type="heading", text=f"Heading level {level}: {text}",
                                            issue="review" if paragraph_finding else None,
                                            finding_id=paragraph_finding.id if paragraph_finding else None))
                else:
                    items.append(ReaderItem(type="paragraph", text=text, issue="review" if paragraph_finding else None,
                                            finding_id=paragraph_finding.id if paragraph_finding else None))
            for link_index, link in enumerate(iter_link_elements(block._p)):
                label = visible_text(link).strip()
                if label:
                    issue = link_label_issue(label)
                    fid = f"link-{para_index:03d}-{link_index + 1:03d}"
                    items.append(ReaderItem(type="link", text=f"Link: {label}", issue=issue, finding_id=fid if issue else None))
        else:
            table_index = table_numbers[block._tbl]
            rows = table_rows(block._tbl)
            columns = max((len(row.xpath("./w:tc")) for row in rows), default=0)
            header = bool(rows and word_flag(rows[0], "w:trPr/w:tblHeader"))
            items.append(ReaderItem(type="table", text=f"Table, {columns} columns, {len(rows)} rows, header row: {'yes' if header else 'no'}",
                                    issue="missing" if rows and not header else None,
                                    finding_id=f"table-{table_index:03d}" if rows and not header else None))
            if rows and not header:
                for ri, row in enumerate(rows, 1):
                    for ci, cell in enumerate(row.xpath("./w:tc"), 1):
                        value = " ".join(visible_text(p).strip() for p in cell.xpath("./w:p") if visible_text(p).strip())
                        items.append(ReaderItem(type="cell", text=f"Row {ri}, Column {ci}: {value}"))
    return ReaderPreview(version=version, items=items)
