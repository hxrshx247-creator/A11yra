import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.audit.links import check_links
from scripts.make_fixtures import add_link


def test_broken_fixture_has_generic_link(broken_doc):
    check, findings = check_links(broken_doc)
    assert check.result == "issues"
    finding, = findings
    assert finding.locator == {"paragraph_index": 3, "link_index": 0}
    assert finding.fixable == "teacher_approved"


def test_clean_fixture_has_descriptive_link(clean_doc):
    check, findings = check_links(clean_doc)
    assert check.result == "passed"
    assert not findings


@pytest.mark.parametrize("label", [" CLICK  HERE! ", "here", "Link", "https://example.org/a", "www.example.org"])
def test_flags_generic_text_and_raw_addresses_in_a_table(label):
    document = Document()
    document.add_paragraph("Intro")
    paragraph = document.add_table(rows=1, cols=1).cell(0, 0).paragraphs[0]
    add_link(paragraph, "Weekly study group schedule")
    add_link(paragraph, label)

    check, findings = check_links(document)

    assert check.result == "issues"
    finding, = findings
    assert finding.locator == {"paragraph_index": 1, "link_index": 1}
    assert "example.org" not in finding.evidence


def test_reads_text_from_simple_hyperlink_field():
    document = Document()
    paragraph = document.add_paragraph()
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), ' HYPERLINK "https://example.org" ')
    field.append(paragraph.add_run("Click ")._r)
    field.append(paragraph.add_run("here")._r)
    paragraph._p.append(field)

    check, findings = check_links(document)

    assert check.result == "issues"
    assert len(findings) == 1


def test_unlinked_url_is_plain_text():
    document = Document()
    document.add_paragraph("https://example.org")
    check, findings = check_links(document)
    assert check.result == "not_evaluated"
    assert not findings
