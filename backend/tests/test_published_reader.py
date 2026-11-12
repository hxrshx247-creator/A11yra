from base64 import b64encode
from hashlib import sha256
from io import BytesIO
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from docx import Document
from docx.oxml.ns import qn

from app.core.config import DOCX_MIME
from app.export.html_export import _clean_fragment
from scripts.make_fixtures import add_link, attendance_chart


def test_published_reader_treats_docx_markup_as_text(client):
    word = Document()
    word.core_properties.title = "Reader security fixture"
    word.add_heading("Accessible heading", level=1)
    word.add_paragraph("<script>fixture-only</script>")
    long_text = "long-reader-text " * 4000
    word.add_paragraph(long_text)
    alt = '<img src="fixture" onerror="fixture-only">'
    word.add_picture(attendance_chart())._inline.docPr.set("descr", alt)
    paragraph = word.add_paragraph()
    add_link(paragraph, "Unsafe link label")
    relationship = paragraph.part.rels[paragraph._p[-1].get(qn("r:id"))]
    relationship._target = "javascript:void(0)"
    add_link(paragraph, "Safe link label")
    paragraph._p[-1].set("onclick", "fixture-only")
    output = BytesIO()
    word.save(output)

    uploaded = client.post("/api/documents", files={"file": ("reader-security.docx", output.getvalue(), DOCX_MIME)})
    assert uploaded.status_code == 201
    document = uploaded.json()["document_id"]
    share = client.post(f"/api/documents/{document}/shares", json={"days": 1})
    assert share.status_code == 201
    response = client.get(urlsplit(share.json()["url"]).path)
    assert response.status_code == 200

    page = BeautifulSoup(response.content, "html.parser")
    article = page.article
    assert article.find(["script", "iframe", "object", "form", "style"]) is None
    assert all(not name.startswith("on") and name != "style" for tag in article.find_all(True) for name in tag.attrs)
    assert "<script>fixture-only</script>" in article.get_text()
    assert article.img["alt"] == alt
    assert long_text.strip() in article.get_text()
    assert article.select_one('h1[id="section-1"]').get_text() == "Accessible heading"
    assert "Unsafe link label" in article.get_text()
    assert [link.get_text() for link in article.find_all("a")] == ["Safe link label"]
    assert article.a["rel"] == ["noopener", "noreferrer"]

    csp = response.headers["content-security-policy"]
    for element, directive in ((page.style, "style-src"), (page.script, "script-src")):
        hashed = b64encode(sha256(element.string.encode()).digest()).decode()
        assert f"{directive} 'sha256-{hashed}'" in csp
    for directive in ("default-src 'none'", "img-src 'self' data:", "font-src 'self' data:",
                      "base-uri 'none'", "form-action 'none'", "frame-ancestors 'none'"):
        assert directive in csp
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_fragment_allowlist_removes_active_markup():
    fragment = BeautifulSoup(
        '<p style="color: red" onclick="fixture">Readable text</p>'
        '<form><input name="fixture"></form><object></object><iframe></iframe><script>fixture</script>'
        '<a href="data:text/plain,fixture">Inert label</a>'
        '<img alt="" src="data:image/png;base64,%%%">'
        '<img alt="" src="data:image/png;base64,dGVzdA==">'
        '<img alt="" src="data:image/svg+xml;base64,dGVzdA==">', "html.parser",
    )
    _clean_fragment(fragment, {})
    assert str(fragment) == "<p>Readable text</p>Inert label"
