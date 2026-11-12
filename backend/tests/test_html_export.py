from io import BytesIO

from bs4 import BeautifulSoup
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml.etree import SubElement

from app.audit.images import DECORATIVE_TAG
from app.core.config import DOCX_MIME
from app.export.html_export import convert_docx_to_html
from scripts.make_fixtures import add_link, attendance_chart


def render(document):
    file = BytesIO()
    document.save(file)
    return BeautifulSoup(convert_docx_to_html(file.getvalue()), "html.parser")


def test_semantic_html_preserves_metadata_and_clean_handout(clean_doc):
    caption = OxmlElement("w:tblCaption")
    caption.set(qn("w:val"), "Study group rooms")
    clean_doc.tables[0]._tbl.tblPr.append(caption)
    clean_doc.add_heading("Schedule details", level=2)
    custom = clean_doc.styles.add_style("Schedule subsection", WD_STYLE_TYPE.PARAGRAPH)
    custom.base_style = clean_doc.styles["Heading 3"]
    clean_doc.add_paragraph("Rooms", style=custom)

    html = render(clean_doc)

    assert html.title.get_text() == "Study group handout"
    assert html.html["lang"] == "en-US"
    assert html.body.a["href"] == "#main"
    assert html.main["tabindex"] == "-1"
    assert [(h.name, h["id"], h["tabindex"]) for h in html.article.find_all(["h1", "h2", "h3"])] == [
        ("h1", "section-1", "-1"),
        ("h2", "section-2", "-1"),
        ("h3", "section-3", "-1"),
    ]
    assert html.figure.img["src"].startswith("data:image/png;base64,")
    assert html.figure.img["alt"] == "Study group attendance doubled from 12 students on Monday to 24 on Thursday."
    assert html.figure.details.summary.get_text() == "Image description"
    assert html.figure.details.p.get_text() == html.figure.img["alt"]
    assert html.table.caption.get_text() == "Study group rooms"
    assert [(cell.get_text(), cell["scope"]) for cell in html.table.thead.find_all("th")] == [
        ("Day", "col"), ("Room", "col"),
    ]
    link = html.article.find("a", href="https://example.org/study-schedule")
    assert link.get_text() == "Weekly study group schedule"


def test_decorative_marker_overrides_stale_word_description(clean_doc):
    properties = clean_doc.inline_shapes[0]._inline.docPr
    marker = SubElement(properties, DECORATIVE_TAG)
    marker.set("val", "1")

    html = render(clean_doc)

    assert html.figure.img["alt"] == ""
    assert html.figure.details is None


def test_inline_picture_has_a_disclosure_outside_the_paragraph(clean_doc):
    paragraph = clean_doc.add_paragraph("Compare attendance in this chart. ")
    picture = paragraph.add_run().add_picture(attendance_chart())
    picture._inline.docPr.set("descr", "Monday had 12 students.")

    html = render(clean_doc)

    picture = html.find("img", alt="Monday had 12 students.")
    assert picture.parent.name == "p"
    assert picture.parent.find_next_sibling().name == "details"
    assert picture.parent.find_next_sibling().p.get_text() == picture["alt"]


def test_missing_metadata_is_not_invented_and_disabled_header_stays_a_data_cell(broken_doc):
    picture = broken_doc.inline_shapes[0]._inline.docPr
    picture.set("title", "A drawing name")
    for row, active in zip(broken_doc.tables[0].rows, ("0", "1")):
        flag = OxmlElement("w:tblHeader")
        flag.set(qn("w:val"), active)
        row._tr.get_or_add_trPr().append(flag)

    html = render(broken_doc)

    assert html.html["lang"] == "und"
    assert html.title.get_text() == "Word document"
    assert html.article.find(["h1", "h2"]) is None
    assert html.figure.img["alt"] == "Image without a description"
    assert html.table.find("th") is None
    assert html.table.tr.td.get_text() == "Day"


def test_html_keeps_internal_bookmarks_and_strips_unsafe_links(clean_doc):
    heading = clean_doc.paragraphs[0]
    bookmark = OxmlElement("w:bookmarkStart")
    bookmark.set(qn("w:id"), "10")
    bookmark.set(qn("w:name"), "top")
    heading._p.append(bookmark)

    paragraph = clean_doc.add_paragraph()
    add_link(paragraph, "Unsafe destination")
    unsafe = paragraph.part.relate_to("javascript:alert(1)", RT.HYPERLINK, is_external=True)
    paragraph.hyperlinks[0]._element.set(qn("r:id"), unsafe)
    add_link(paragraph, "Back to top")
    internal = paragraph.hyperlinks[1]._element
    del internal.attrib[qn("r:id")]
    internal.set(qn("w:anchor"), "top")
    clean_doc.add_paragraph("<script>Literal code example</script>")

    html = render(clean_doc)

    assert html.find("script") is None
    assert "<script>Literal code example</script>" in html.article.get_text()
    assert "Unsafe destination" in html.article.get_text()
    assert html.find("a", href="javascript:alert(1)") is None
    assert html.find("a", href="#docx-top").get_text() == "Back to top"
    assert html.find(id="docx-top") is not None


def test_converter_reads_the_actual_repaired_docx_download(client, fixture_paths):
    path = fixture_paths[0]
    upload = client.post("/api/documents", files={"file": (path.name, path.read_bytes(), DOCX_MIME)})
    url = f"/api/documents/{upload.json()['document_id']}"
    repairs = client.post(f"{url}/fixes", json={"fixes": [
        {"finding_id": "title-missing", "type": "set_title", "payload": {"title": "Learner handout"}},
        {"finding_id": "language-default-missing", "type": "set_language", "payload": {"lang": "en-IN"}},
        {"finding_id": "img-001", "type": "set_alt_text", "payload": {"alt_text": "Attendance doubled."}},
    ]})
    assert len(repairs.json()["applied"]) == 3
    reaudited = client.post(f"{url}/reaudit")
    assert len(reaudited.json()["diff"]["verified_fixed"]) == 3
    repaired = client.get(f"{url}/export/docx")
    assert repaired.status_code == 200

    html = BeautifulSoup(convert_docx_to_html(repaired.content), "html.parser")

    assert html.title.get_text() == "Learner handout"
    assert html.html["lang"] == "en-IN"
    assert html.img["alt"] == "Attendance doubled."
