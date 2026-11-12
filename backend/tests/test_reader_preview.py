from uuid import uuid4
from pathlib import Path

from docx import Document

from app.audit.reader_preview import build_reader_preview
from app.audit.runner import run_audit
from app.models import Fix, FixPayload
from app.repair.service import apply_fixes
from scripts.make_fixtures import make_messy_handout


def test_original_and_repaired_preview_readout():
    lecture = Document(Path(__file__).resolve().parents[1] / "fixtures" / "stack-queue-lecture.docx")
    audit = run_audit(lecture, uuid4())
    original = build_reader_preview(lecture, audit, "original")
    text = [item.text for item in original.items]
    assert "Document title: none (file name will be read instead)" in text
    assert "Language: not set" in text
    assert "Image: no description" in text
    assert "Link: click here" in text

    apply_fixes(lecture, audit, [
        Fix(finding_id="title-missing", type="set_title", payload=FixPayload(title="Stack and queue")),
        Fix(finding_id="language-default-missing", type="set_language", payload=FixPayload(lang="en-IN")),
        Fix(finding_id="img-001", type="set_alt_text", payload=FixPayload(alt_text="Attendance doubled.")),
        Fix(finding_id="link-090-001", type="set_link_text", payload=FixPayload(new_text="Stack and queue reference")),
    ])
    repaired_audit = run_audit(lecture, uuid4())
    repaired = build_reader_preview(lecture, repaired_audit, "repaired")
    readout = [item.text for item in repaired.items]
    assert "Document title: none (file name will be read instead)" not in readout
    assert "Language: not set" not in readout
    assert "Image: no description" not in readout
    assert "Link: click here" not in readout


def test_messy_handout_fixture_contains_review_choices(tmp_path):
    path = make_messy_handout(tmp_path / "messy.docx")
    document = Document(path)
    audit = run_audit(document, uuid4())
    assert any(item.id.startswith("heading-skip-") for item in audit.findings)
    assert any(item.check_id == "images" and item.status == "needs_review" for item in audit.findings)
    assert len([item for item in audit.findings if item.check_id == "links"]) == 2
    assert any(item.check_id == "tables" for item in audit.findings)
