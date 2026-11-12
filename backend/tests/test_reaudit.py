from io import BytesIO
from uuid import uuid4

from docx import Document

from app.audit.reaudit import compare_audits
from app.audit.runner import run_audit
from app.core.config import DOCX_MIME
from app.main import app
from app.models import Audit, ReauditResponse, UploadResponse


def test_reaudit_verifies_five_repairs_and_preserves_heading_findings(client, fixture_paths):
    source = fixture_paths[0]
    uploaded = client.post("/api/documents", files={"file": (source.name, source.read_bytes(), DOCX_MIME)})
    before = UploadResponse.model_validate(uploaded.json())
    url = f"/api/documents/{before.document_id}"
    repairs = [
        ("title-missing", "set_title", {"title": "Study group handout"}),
        ("language-default-missing", "set_language", {"lang": "en-IN"}),
        ("img-001", "set_alt_text", {"alt_text": "Attendance doubled from 12 to 24 students."}),
        ("link-004-001", "set_link_text", {"new_text": "Weekly study group schedule"}),
        ("table-001", "set_table_header", {}),
    ]
    fixed = client.post(f"{url}/fixes", json={"fixes": [
        {"finding_id": finding_id, "type": repair_type, "payload": payload}
        for finding_id, repair_type, payload in repairs
    ]})
    assert fixed.status_code == 200
    assert len(fixed.json()["applied"]) == 5
    assert {item["status"] for item in fixed.json()["applied"]} == {"fixed_unverified"}

    response = client.post(f"{url}/reaudit")

    assert response.status_code == 200
    result = ReauditResponse.model_validate(response.json())
    assert result.audit.audit_id != before.audit.audit_id
    assert result.diff.progress_before.percent == 0
    assert result.diff.progress_after.model_dump() == {"passed": 5, "evaluated": 6, "percent": 83}
    assert set(result.diff.verified_fixed) == {item[0] for item in repairs}
    assert result.diff.still_open == ["headings-missing"]
    assert result.diff.needs_review == ["heading-lookalike-001"]
    assert result.diff.new_findings == []
    assert Audit.model_validate(client.get(f"{url}/audit").json()) == result.audit

    repeated = ReauditResponse.model_validate(client.post(f"{url}/reaudit").json())
    assert repeated.diff.verified_fixed == []
    assert sum(finding.status == "verified_fixed" for finding in repeated.audit.findings) == 5

    download = client.get(f"{url}/export/docx")
    assert download.status_code == 200
    assert download.headers["content-type"] == DOCX_MIME
    assert download.headers["content-disposition"] == 'attachment; filename="a11yra-repaired.docx"'
    repaired = Document(BytesIO(download.content))
    assert repaired.core_properties.title == "Study group handout"
    assert run_audit(repaired, before.document_id).progress == result.audit.progress
    assert client.get(f"{url}/audit").status_code == 200
    assert (app.state.documents.root / str(before.document_id)).exists()


def test_reappearing_finding_and_unconfirmed_fix(broken_doc):
    document_id = uuid4()
    previous = run_audit(broken_doc, document_id)
    statuses = {finding.id: finding for finding in previous.findings}
    statuses["title-missing"].status = "verified_fixed"
    statuses["img-001"].status = "fixed_unverified"
    picture = broken_doc.inline_shapes[0]._inline
    picture.getparent().remove(picture)

    fresh = run_audit(broken_doc, document_id)
    diff = compare_audits(previous, fresh)

    assert diff.new_findings == ["title-missing"]
    assert "img-001" in diff.needs_review
    assert diff.verified_fixed == []
    by_id = {finding.id: finding for finding in fresh.findings}
    assert by_id["title-missing"].status == "open"
    assert by_id["img-001"].status == "fixed_unverified"


def test_repair_that_still_triggers_check_reopens(broken_doc):
    document_id = uuid4()
    previous = run_audit(broken_doc, document_id)
    next(finding for finding in previous.findings if finding.id == "title-missing").status = "fixed_unverified"
    fresh = run_audit(broken_doc, document_id)
    diff = compare_audits(previous, fresh)
    assert "title-missing" in diff.still_open
    assert "title-missing" not in diff.verified_fixed


def test_reaudit_missing_session(client):
    response = client.post(f"/api/documents/{uuid4()}/reaudit")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
