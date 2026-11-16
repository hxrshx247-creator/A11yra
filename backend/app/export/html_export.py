"""Convert a repaired Word handout to semantic HTML without changing the source."""

import re
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from io import BytesIO
from urllib.parse import urlsplit
from uuid import uuid4

import mammoth
from bs4 import BeautifulSoup, Comment
from docx import Document
from docx.document import Document as WordDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.audit._body import word_flag, word_value
from app.audit.headings import _heading_level, _style_chain
from app.audit.images import _is_decorative, iter_picture_properties
from app.audit.language import DEFAULT_LANGUAGE_PATH, primary_language
from app.audit.tables import body_tables, table_rows
from app.export.preview_flags import insert_preview_flags, render_preview_flags
from app.models import Finding

HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
ALLOWED_TAGS = {
    *HEADINGS, "a", "blockquote", "br", "caption", "code", "dd", "del", "div",
    "dl", "dt", "em", "hr", "img", "li", "ol", "p", "pre", "s", "span",
    "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
DROP_TAGS = {"audio", "embed", "form", "iframe", "math", "object", "script", "style", "svg", "template", "video"}
RASTER_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
    "image/bmp": (b"BM",),
}
MISSING_ALT = "Image without a description"


def _metadata(document: WordDocument) -> tuple[str, str]:
    try:
        title = document.part.package.part_related_by(RT.CORE_PROPERTIES).core_properties.title.strip()
    except KeyError:
        title = ""
    try:
        styles = document.part.part_related_by(RT.STYLES).styles
        language = (word_value(styles.element, DEFAULT_LANGUAGE_PATH) or "").strip()
    except KeyError:
        language = None
    return title or "Word document", language if primary_language(language) and language.isascii() else "und"


def _heading_style_map(document: WordDocument) -> list[str]:
    try:
        styles = document.part.part_related_by(RT.STYLES).styles
    except KeyError:
        return []

    mappings = []
    for style in styles:
        if style.type != WD_STYLE_TYPE.PARAGRAPH or not style.style_id or re.search(r"[\r\n]", style.style_id):
            continue
        level = _heading_level(_style_chain(style))
        if level is not None:
            # Escape style IDs as Mammoth matcher tokens, not as CSS selectors.
            style_id = re.sub(r"[^a-zA-Z0-9_-]", lambda match: "\\" + match[0], style.style_id)
            if re.match(r"[0-9]", style_id):
                style_id = "\\" + style_id
            mappings.append(f"p.{style_id} => h{min(level, 6)}:fresh")
    return mappings


def _prepare_tables(document: WordDocument, marker: str) -> tuple[list[str], dict[str, str]]:
    mappings = []
    captions = {}
    for index, table in enumerate(body_tables(document)):
        for row in table_rows(table):
            # Mammoth uses presence alone to decide whether a row is a header.
            if word_flag(row, "w:trPr/w:tblHeader") is False:
                properties = row.find(qn("w:trPr"))
                properties.remove(properties.find(qn("w:tblHeader")))

        caption = (word_value(table, "w:tblPr/w:tblCaption") or "").strip()
        if not caption:
            continue
        key = f"{marker}-{index}"
        properties = table.find(qn("w:tblPr"))
        style = properties.find(qn("w:tblStyle"))
        if style is None:
            style = OxmlElement("w:tblStyle")
            properties.insert(0, style)
        style.set(qn("w:val"), key)
        mappings.append(f"table.{key} => table.{key}:fresh")
        captions[key] = caption
    return mappings, captions


def _image_converter(decorative_marker: str):
    @mammoth.images.img_element
    def convert(image):
        alt = (image.alt_text or "").strip()
        if alt == decorative_marker:
            alt = ""
        elif not alt:
            alt = MISSING_ALT
        attributes = {"alt": alt}
        if image.content_type in RASTER_SIGNATURES:
            with image.open() as image_file:
                encoded = b64encode(image_file.read()).decode("ascii")
            attributes["src"] = f"data:{image.content_type};base64,{encoded}"
        return attributes
    return convert


def _safe_link(href: str) -> bool:
    if not href or any(ord(char) < 32 or ord(char) == 127 for char in href):
        return False
    if href.startswith("#"):
        return True
    try:
        url = urlsplit(href)
        return (url.scheme in {"http", "https"} and bool(url.hostname)) or (
            url.scheme == "mailto" and bool(url.path)
        )
    except ValueError:
        return False


def _safe_image(src: str) -> bool:
    header, separator, payload = src.partition(",")
    if not separator or not header.startswith("data:") or not header.endswith(";base64"):
        return False
    media_type = header[5:-7]
    signatures = RASTER_SIGNATURES.get(media_type)
    if signatures is None:
        return False
    try:
        data = b64decode(payload, validate=True)
    except Base64Error:
        return False
    return data.startswith(signatures) and (media_type != "image/webp" or data[8:12] == b"WEBP")


def _clean_fragment(fragment: BeautifulSoup, captions: dict[str, str]) -> None:
    for tag in fragment.find_all(DROP_TAGS):
        if tag.parent is not None:
            tag.decompose()
    for comment in fragment.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()

    for tag in fragment.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue

        attrs = tag.attrs
        tag.attrs = {}
        if attrs.get("id", "").startswith("docx-"):
            tag["id"] = attrs["id"]
        if tag.name == "a":
            href = attrs.get("href", "").strip()
            if _safe_link(href):
                tag["href"] = href
                if not href.startswith("#"):
                    tag["rel"] = "noopener noreferrer"
            elif "id" not in tag.attrs:
                tag.unwrap()
        elif tag.name == "img":
            alt = attrs.get("alt", MISSING_ALT)
            src = attrs.get("src", "")
            if _safe_image(src):
                tag["src"] = src
                tag["alt"] = alt
            elif alt:
                tag.replace_with(f"Image unavailable: {alt}")
            else:
                tag.decompose()
        elif tag.name in {"th", "td"}:
            for name in ("rowspan", "colspan"):
                if re.fullmatch(r"[1-9][0-9]{0,3}", attrs.get(name, "")):
                    tag[name] = attrs[name]
            if tag.name == "th":
                tag["scope"] = "col"
        elif tag.name == "table":
            caption = next((captions[key] for key in attrs.get("class", []) if key in captions), None)
            if caption:
                element = fragment.new_tag("caption")
                element.string = caption
                tag.insert(0, element)


def _add_sections_and_figures(fragment: BeautifulSoup) -> None:
    for index, heading in enumerate(fragment.find_all(HEADINGS), start=1):
        heading["id"] = f"section-{index}"
        heading["tabindex"] = "-1"

    last_disclosures = {}
    for image in fragment.find_all("img"):
        paragraph = image.find_parent("p")
        if paragraph and not paragraph.get_text(strip=True) and len(paragraph.find_all("img")) == 1:
            paragraph.name = "figure"

        if not image["alt"] or image["alt"] == MISSING_ALT:
            continue
        disclosure = fragment.new_tag("details")
        summary = fragment.new_tag("summary")
        summary.string = "Image description"
        description = fragment.new_tag("p")
        description.string = image["alt"]
        disclosure.extend([summary, description])
        block = image.find_parent([*HEADINGS, "p", "figure", "li", "td", "th"])
        if block and block.name in {*HEADINGS, "p"}:
            # Keep a disclosure beside inline text without putting block markup inside it.
            previous = last_disclosures.get(id(block), block)
            previous.insert_after(disclosure)
            last_disclosures[id(block)] = disclosure
        else:
            (block or fragment).append(disclosure)


def convert_docx_to_html(contents: bytes, *, flags: list[Finding] | None = None) -> str:
    """Return a complete HTML document from a validated or repaired DOCX."""
    document = Document(BytesIO(contents))
    title, language = _metadata(document)
    marker = f"a11yra-{uuid4().hex}"
    if flags:
        insert_preview_flags(document, flags, marker)
    for _, properties in iter_picture_properties(document):
        if properties is None:
            continue
        properties.attrib.pop("title", None)
        if _is_decorative(properties):
            properties.set("descr", marker)

    table_mappings, captions = _prepare_tables(document, marker)
    conversion_input = BytesIO()
    document.save(conversion_input)
    conversion_input.seek(0)
    result = mammoth.convert_to_html(
        conversion_input,
        style_map="\n".join([*_heading_style_map(document), *table_mappings]),
        include_embedded_style_map=False,
        external_file_access=False,
        id_prefix="docx-",
        convert_image=_image_converter(marker),
    )

    fragment = BeautifulSoup(result.value, "html.parser")
    _clean_fragment(fragment, captions)
    _add_sections_and_figures(fragment)

    page = BeautifulSoup(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; img-src data:; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title></title>'
        '</head><body><a href="#main">Skip to content</a><header><p></p></header>'
        '<main id="main" tabindex="-1"><article></article></main></body></html>',
        "html.parser",
    )
    page.html["lang"] = language
    page.title.string = title
    page.header.p.string = title
    page.article.extend(list(fragment.contents))
    if flags:
        render_preview_flags(page, flags, marker)
    return str(page)
