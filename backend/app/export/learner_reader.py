from base64 import b64decode, b64encode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from bs4 import BeautifulSoup

from app.export.html_export import HEADINGS, convert_docx_to_html

READER_DIR = Path(__file__).resolve().parents[3] / "reader"


def _csp_hash(source: str) -> str:
    digest = b64encode(sha256(source.encode("utf-8")).digest()).decode("ascii")
    return f"'sha256-{digest}'"


def _inline_policy(stylesheet: str, javascript: str) -> str:
    return (
        f"default-src 'none'; style-src {_csp_hash(stylesheet)}; script-src {_csp_hash(javascript)}; "
        "img-src 'self' data:; font-src 'self' data:; base-uri 'none'; form-action 'none'"
    )


def published_reader_policy(snapshot: bytes) -> str:
    # Published files contain the reader assets from the day they were created.
    page = BeautifulSoup(snapshot, "html.parser", from_encoding="utf-8")
    if page.style is None or page.script is None:
        return "default-src 'none'; frame-ancestors 'none'"
    return _inline_policy(page.style.get_text(), page.script.get_text()) + "; frame-ancestors 'none'"


def _reader_page(contents: bytes) -> BeautifulSoup:
    document = BeautifulSoup(convert_docx_to_html(contents), "html.parser")
    page = BeautifulSoup((READER_DIR / "reader.html").read_text(encoding="utf-8"), "html.parser")
    page.html["lang"] = document.html["lang"]
    page.title.string = document.title.get_text()
    page.select_one("#document-title").string = document.title.get_text()
    page.article.extend(list(document.article.contents))

    if page.article.h1 is None:
        title = page.new_tag("h1", attrs={"class": "reader-title-fallback"})
        title.string = document.title.get_text()
        page.article.insert_before(title)
    if not page.article.get_text(strip=True) and not page.article.find(["img", "table"]):
        empty = page.new_tag("p")
        empty.string = "This document has no text or pictures to display."
        page.article.append(empty)

    headings = page.article.find_all(HEADINGS)
    contents_list = page.select_one("#contents-list")
    for index, heading in enumerate(headings, start=1):
        item = page.new_tag("li", attrs={"data-level": heading.name[1]})
        link = page.new_tag("a", href=f"#{heading['id']}")
        link.string = heading.get_text(" ", strip=True) or f"Section {index}"
        item.append(link)
        contents_list.append(item)
    if not headings:
        del page.select_one("#contents-empty")["hidden"]
        contents_list["hidden"] = ""

    for index, table in enumerate(page.article.find_all("table"), start=1):
        caption = table.find("caption", recursive=False)
        label = caption.get_text(" ", strip=True) if caption else f"Table {index}"
        wrapper = page.new_tag("div", attrs={
            "class": "table-scroll", "role": "region", "aria-label": label, "tabindex": "0",
        })
        table.wrap(wrapper)
    return page


def render_learner_html(contents: bytes) -> str:
    """Render the learner page as a single file with local assets."""
    page = _reader_page(contents)
    stylesheet = (READER_DIR / "reader.css").read_text(encoding="utf-8")
    javascript = (READER_DIR / "reader.js").read_text(encoding="utf-8")
    _set_policy(page, _inline_policy(stylesheet, javascript))
    style = page.new_tag("style")
    style.string = stylesheet
    page.head.append(style)
    script = page.new_tag("script")
    script.string = javascript
    page.body.append(script)
    return str(page)


def _set_policy(page: BeautifulSoup, policy: str) -> None:
    page.head.insert(1, page.new_tag("meta", attrs={
        "http-equiv": "Content-Security-Policy", "content": policy,
    }))


def render_learner_bundle(contents: bytes) -> bytes:
    """Package the reader HTML and its sibling assets for local use."""
    page = _reader_page(contents)
    _set_policy(
        page,
        "default-src 'none'; img-src 'self' file:; style-src 'self' file:; "
        "script-src 'self' file:; base-uri 'none'; form-action 'none'",
    )
    page.head.append(page.new_tag("link", rel="stylesheet", href="reader.css"))
    page.body.append(page.new_tag("script", src="reader.js"))

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        images: set[str] = set()
        for image in page.article.find_all("img"):
            header, encoded = image["src"].split(",", 1)
            extension = header.removeprefix("data:image/").removesuffix(";base64")
            data = b64decode(encoded, validate=True)
            path = f"images/{sha256(data).hexdigest()}.{extension}"
            if path not in images:
                archive.writestr(path, data)
                images.add(path)
            image["src"] = path

        archive.writestr("index.html", str(page))
        for filename in ("reader.css", "reader.js"):
            archive.writestr(filename, (READER_DIR / filename).read_bytes())
    return output.getvalue()
