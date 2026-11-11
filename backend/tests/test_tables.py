from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.audit.tables import check_tables


def mark_header(row, value=None):
    marker = OxmlElement("w:tblHeader")
    if value is not None:
        marker.set(qn("w:val"), value)
    row._tr.get_or_add_trPr().append(marker)


def test_broken_fixture_notes_bold_first_row_without_header(broken_doc):
    check, findings = check_tables(broken_doc)
    assert check.result == "issues"
    finding, = findings
    assert finding.locator == {"table_index": 0}
    assert "bold" in finding.evidence
    assert finding.fixable == "teacher_approved"


def test_clean_fixture_has_header(clean_doc):
    check, findings = check_tables(clean_doc)
    assert check.result == "passed"
    assert not findings


def test_disabled_first_header_and_marked_later_row_do_not_pass():
    document = Document()
    table = document.add_table(rows=2, cols=2)
    mark_header(table.rows[0], "0")
    mark_header(table.rows[1], "1")

    check, findings = check_tables(document)

    assert check.result == "issues"
    finding, = findings
    assert "later row" in finding.evidence


def test_nested_header_cannot_satisfy_outer_table():
    document = Document()
    outer = document.add_table(rows=2, cols=2)
    inner = outer.cell(0, 0).add_table(rows=2, cols=2)
    mark_header(inner.rows[0])

    check, findings = check_tables(document)

    assert check.result == "issues"
    assert [finding.locator for finding in findings] == [{"table_index": 0}]


def test_no_tables_is_not_evaluated():
    check, findings = check_tables(Document())
    assert check.result == "not_evaluated"
    assert not findings
