from uuid import uuid4

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt

from app.audit.headings import check_headings
from app.audit.runner import run_audit
from app.audit.reaudit import compare_audits
from app.models import Fix, FixPayload
from app.repair.service import apply_fixes


def test_broken_fixture_flags_missing_and_visual_headings(broken_doc):
    check, findings = check_headings(broken_doc)
    assert check.result == "issues"
    assert check.finding_ids == ["headings-missing", "heading-lookalike-001"]
    assert [finding.status for finding in findings] == ["open", "needs_review"]
    assert findings[0].fixable == "recommendation_only"
    assert findings[1].fixable == "teacher_approved"


def test_clean_fixture_has_a_heading_outline(clean_doc):
    check, findings = check_headings(clean_doc)
    assert check.result == "passed"
    assert not findings


def test_flags_initial_and_later_gaps_but_allows_return_to_higher_level():
    document = Document()
    for level in (2, 3, 1, 3, 2):
        document.add_heading("Section", level=level)

    check, findings = check_headings(document)

    assert check.result == "issues"
    assert [finding.locator["paragraph_index"] for finding in findings] == [0, 3]
    assert all(finding.confidence == "high" for finding in findings)


def test_inherited_heading_style_counts():
    document = Document()
    style = document.styles.add_style("Handout section", WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = document.styles["Heading 1"]
    document.add_paragraph("Section", style=style)
    check, _ = check_headings(document)
    assert check.result == "passed"


def test_only_the_large_standalone_paragraph_needs_review():
    document = Document()
    document.add_paragraph("Handout", style="Title")
    document.add_heading("Section", level=1)
    document.add_paragraph("Key dates").runs[0].font.size = Pt(20)
    document.add_paragraph("Important.").runs[0].bold = True
    document.add_paragraph("Item", style="List Bullet").runs[0].bold = True
    document.add_table(rows=1, cols=1).cell(0, 0).paragraphs[0].add_run("Date").bold = True

    check, findings = check_headings(document)

    assert check.result == "needs_review"
    finding, = findings
    assert finding.locator == {"paragraph_index": 2}


def test_blank_document_has_no_heading_content_to_evaluate():
    document = Document()
    document.add_paragraph("  ")
    check, findings = check_headings(document)
    assert check.result == "not_evaluated"
    assert not findings


def test_teacher_approved_heading_candidate_uses_a_real_word_style():
    document = Document()
    document.add_heading("Stack", level=1)
    paragraph = document.add_paragraph("Push and pop")
    paragraph.runs[0].bold = True
    audit = run_audit(document, uuid4())
    finding = next(item for item in audit.findings if item.id == "heading-lookalike-002")
    assert finding.fixable == "teacher_approved"
    fix = Fix(finding_id=finding.id, type="set_heading", payload=FixPayload(heading_level=2))

    result = apply_fixes(document, audit, [fix])

    assert [item.finding_id for item in result.applied] == [finding.id]
    assert document.paragraphs[1].style.name == "Heading 2"
    assert check_headings(document)[0].result == "passed"
    fresh = run_audit(document, uuid4())
    assert finding.id in compare_audits(audit, fresh).verified_fixed


def test_unapproved_heading_candidate_is_left_unchanged():
    document = Document()
    paragraph = document.add_paragraph("Possible section")
    paragraph.runs[0].bold = True
    audit = run_audit(document, uuid4())
    candidate = next(item for item in audit.findings if item.id.startswith("heading-lookalike"))
    before = paragraph.style.name
    assert candidate.fixable == "teacher_approved"
    assert paragraph.style.name == before == "Normal"
