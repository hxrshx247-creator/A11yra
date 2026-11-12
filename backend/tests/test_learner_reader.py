from io import BytesIO

from bs4 import BeautifulSoup
from docx import Document

from app.export.learner_reader import render_learner_html


def render(document):
    file = BytesIO()
    document.save(file)
    return BeautifulSoup(render_learner_html(file.getvalue()), "html.parser")


def test_reader_contents_link_to_real_headings_and_tables_have_named_regions(clean_doc):
    clean_doc.add_heading("Schedule", level=2)
    page = render(clean_doc)

    assert page.nav["aria-label"] == "Contents"
    assert [(link.get_text(), link["href"]) for link in page.nav.find_all("a")] == [
        ("Study group handout", "#section-1"),
        ("Schedule", "#section-2"),
    ]
    assert page.article.h2["id"] == "section-2"
    assert page.table.parent["aria-label"] == "Table 1"
    assert page.table.parent["tabindex"] == "0"
    assert page.script.get("src") is None
    assert page.style.get_text()


def test_reader_explains_when_document_has_no_headings(broken_doc):
    page = render(broken_doc)
    assert not page.nav.find_all("a")
    assert page.select_one("#contents-empty").get("hidden") is None
    assert page.select_one("#contents-empty").get_text() == "This document has no headings."
    assert page.main.h1.get_text() == "Word document"
    assert page.article.h1 is None


def test_empty_reader_has_a_plain_language_message():
    page = render(Document())
    assert page.article.p.get_text() == "This document has no text or pictures to display."
