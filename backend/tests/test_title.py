from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from app.audit.title import check_title


def test_clean_fixture_title_passes(clean_doc):
    check, findings = check_title(clean_doc)
    assert check.result == "passed"
    assert check.finding_ids == findings == []


def test_broken_fixture_title_is_missing(broken_doc):
    check, findings = check_title(broken_doc)
    assert check.result == "issues"
    finding, = findings
    assert check.finding_ids == [finding.id]
    assert finding.locator == {"property": "title"}
    assert finding.status == "open"
    assert finding.fixable == "teacher_approved"


def test_whitespace_title_is_missing_even_with_a_heading(clean_doc):
    clean_doc.core_properties.title = " \t\n"
    check, _ = check_title(clean_doc)
    assert check.result == "issues"


def test_placeholder_title_uses_filename_when_there_is_no_opening_title():
    document = Document()
    document.core_properties.title = "Give a sample title"
    document.add_paragraph("Read the first chapter before the next class.")

    check, (finding,) = check_title(document, "CS101_Reading Guide.docx")

    assert check.result == "issues"
    assert "placeholder text" in finding.evidence
    assert finding.suggested_value == "CS101 Reading Guide"


def test_missing_core_properties_part_is_not_created_during_audit(clean_doc):
    relationships = clean_doc.part.package.rels
    core_id = next(rid for rid, rel in relationships.items() if rel.reltype == RT.CORE_PROPERTIES)
    del relationships[core_id]

    check, _ = check_title(clean_doc)

    assert check.result == "issues"
    assert all(rel.reltype != RT.CORE_PROPERTIES for rel in relationships.values())
