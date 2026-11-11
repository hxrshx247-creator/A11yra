import pytest
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import nsmap, qn

from app.audit.language import check_language


def set_language(properties, tag):
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), tag)
    properties.append(lang)


def test_clean_fixture_has_language(clean_doc):
    check, findings = check_language(clean_doc)
    assert check.result == "passed"
    assert check.finding_ids == findings == []


def test_broken_fixture_is_missing_language(broken_doc):
    check, findings = check_language(broken_doc)
    assert check.result == "issues"
    finding, = findings
    assert check.finding_ids == [finding.id]
    assert finding.locator == {"property": "default_language"}
    assert finding.fixable == "teacher_approved"


@pytest.mark.parametrize("tag", ["  ", "und", "en_US"])
def test_unusable_default_language(clean_doc, tag):
    lang = clean_doc.styles.element.find(
        "w:docDefaults/w:rPrDefault/w:rPr/w:lang", namespaces=nsmap
    )
    lang.set(qn("w:val"), tag)
    check, _ = check_language(clean_doc)
    assert check.result == "issues"


def test_missing_styles_part_is_not_created_during_audit(clean_doc):
    relationships = clean_doc.part.rels
    style_id = next(rid for rid, rel in relationships.items() if rel.reltype == RT.STYLES)
    del relationships[style_id]

    check, _ = check_language(clean_doc)

    assert check.result == "issues"
    assert all(rel.reltype != RT.STYLES for rel in relationships.values())


def test_different_language_in_table_needs_review(clean_doc):
    run = clean_doc.tables[0].cell(1, 0).paragraphs[0].runs[0]
    set_language(run._r.get_or_add_rPr(), "fr-CA")

    check, findings = check_language(clean_doc)

    assert check.result == "needs_review"
    finding, = findings
    assert check.finding_ids == [finding.id]
    assert finding.status == "needs_review"
    assert finding.fixable == "recommendation_only"


def test_regional_variants_of_one_language_do_not_need_review(clean_doc):
    run = clean_doc.paragraphs[1].add_run("Another example")
    set_language(run._r.get_or_add_rPr(), "EN-gb")
    check, _ = check_language(clean_doc)
    assert check.result == "passed"


@pytest.mark.parametrize("style_type", [WD_STYLE_TYPE.CHARACTER, WD_STYLE_TYPE.PARAGRAPH])
def test_language_inherited_from_used_style_needs_review(clean_doc, style_type):
    base = clean_doc.styles.add_style("Spanish base", style_type)
    set_language(base.element.get_or_add_rPr(), "es")
    child = clean_doc.styles.add_style("Spanish quote", style_type)
    child.base_style = base
    paragraph = clean_doc.add_paragraph()
    run = paragraph.add_run("Ejemplo")
    if style_type == WD_STYLE_TYPE.PARAGRAPH:
        paragraph.style = child
    else:
        run.style = child

    check, _ = check_language(clean_doc)
    assert check.result == "needs_review"

    # Direct formatting takes precedence over the inherited language.
    set_language(run._r.get_or_add_rPr(), "en-US")
    check, _ = check_language(clean_doc)
    assert check.result == "passed"


def test_missing_default_keeps_mixed_language_finding(broken_doc):
    run = broken_doc.paragraphs[1].runs[0]
    set_language(run._r.get_or_add_rPr(), "en")
    link_run = broken_doc.paragraphs[-1].hyperlinks[0].runs[0]
    set_language(link_run._r.get_or_add_rPr(), "es")

    check, findings = check_language(broken_doc)

    assert check.result == "issues"
    assert [finding.status for finding in findings] == ["open", "needs_review"]
