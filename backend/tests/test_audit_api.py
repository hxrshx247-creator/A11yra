from os import utime
from time import time
from uuid import uuid4

import pytest

from app.core.config import DOCX_MIME, SESSION_TTL_SECONDS
from app.main import app
from app.models import Audit, UploadResponse


@pytest.mark.parametrize(
    ("fixture_index", "passed", "percent", "finding_count"),
    [(0, 0, 0, 7), (1, 6, 100, 0)],
)
def test_audit_api_returns_saved_fixture_findings(client, fixture_paths, fixture_index, passed, percent, finding_count):
    path = fixture_paths[fixture_index]
    upload_response = client.post(
        "/api/documents", files={"file": (path.name, path.read_bytes(), DOCX_MIME)}
    )
    assert upload_response.status_code == 201
    upload = UploadResponse.model_validate(upload_response.json())
    assert upload_response.headers["cache-control"] == "no-store"

    response = client.get(f"/api/documents/{upload.document_id}/audit")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == upload_response.json()["audit"]
    audit = Audit.model_validate(response.json())
    assert audit == upload.audit
    assert audit.progress.model_dump() == {"passed": passed, "evaluated": 6, "percent": percent}
    assert len(audit.findings) == finding_count
    assert len({finding.id for finding in audit.findings}) == finding_count
    previews = {finding["id"]: finding["preview"] for finding in response.json()["findings"] if "preview" in finding}
    assert previews == ({"heading-lookalike-001": "Study group handout"} if fixture_index == 0 else {})
    for check in audit.checks:
        assert check.finding_ids == [finding.id for finding in audit.findings if finding.check_id == check.id]


@pytest.mark.parametrize("document_id", ["invalid-id", str(uuid4())])
def test_missing_document_returns_contract_error(client, document_id):
    response = client.get(f"/api/documents/{document_id}/audit")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_expired_audit_is_unavailable_before_cleanup_sweep(client, fixture_paths):
    path = fixture_paths[1]
    response = client.post(
        "/api/documents", files={"file": (path.name, path.read_bytes(), DOCX_MIME)}
    )
    document_id = response.json()["document_id"]
    session = app.state.documents.root / document_id
    expired_at = time() - SESSION_TTL_SECONDS - 1
    utime(session / "original.docx", (expired_at, expired_at))

    response = client.get(f"/api/documents/{document_id}/audit")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_reader_preview_uses_original_and_repaired_document_versions(client, fixture_paths):
    source = fixture_paths[0]
    upload = client.post("/api/documents", files={"file": (source.name, source.read_bytes(), DOCX_MIME)}).json()
    url = f"/api/documents/{upload['document_id']}"
    original = client.get(f"{url}/reader-preview?version=original").json()
    assert original["version"] == "original"
    assert "Document title: none (file name will be read instead)" in [item["text"] for item in original["items"]]
    assert "Language: not set" in [item["text"] for item in original["items"]]
    assert "Image: no description" in [item["text"] for item in original["items"]]
    assert "Link: click here" in [item["text"] for item in original["items"]]
    for fix in [
        {"finding_id": "title-missing", "type": "set_title", "payload": {"title": "Study group"}},
        {"finding_id": "language-default-missing", "type": "set_language", "payload": {"lang": "en-IN"}},
        {"finding_id": "img-001", "type": "set_alt_text", "payload": {"alt_text": "Attendance doubled."}},
        {"finding_id": "link-004-001", "type": "set_link_text", "payload": {"new_text": "Study group schedule"}},
    ]:
        assert client.post(f"{url}/fixes", json={"fixes": [fix]}).status_code == 200
    repaired = client.get(f"{url}/reader-preview?version=repaired").json()
    readout = [item["text"] for item in repaired["items"]]
    assert "Document title: Study group" in readout
    assert "Language: en-IN" in readout
    assert "Image: Attendance doubled." in readout
    assert "Link: Study group schedule" in readout


def test_messy_sample_preserves_judgment_findings(client):
    response = client.post("/api/documents/sample?kind=messy")
    assert response.status_code == 201
    audit = Audit.model_validate(response.json()["audit"])
    assert {"title-missing", "language-default-missing"}.issubset({finding.id for finding in audit.findings})
    assert any(finding.id.startswith("heading-skip-") and finding.fixable == "teacher_approved" for finding in audit.findings)
    assert any(finding.check_id == "images" and finding.status == "needs_review" for finding in audit.findings)
    assert len([finding for finding in audit.findings if finding.check_id == "links"]) == 2
    table = next(finding for finding in audit.findings if finding.check_id == "tables")
    assert table.status == "open" and table.fixable == "teacher_approved"


def test_heading_candidate_can_be_dismissed_as_not_a_heading(client, fixture_paths):
    source = fixture_paths[0]
    upload = client.post("/api/documents", files={"file": (source.name, source.read_bytes(), DOCX_MIME)}).json()
    url = f"/api/documents/{upload['document_id']}"
    response = client.post(f"{url}/findings/heading-lookalike-001/dismiss")
    assert response.status_code == 204
    audit = Audit.model_validate(client.get(f"{url}/audit").json())
    finding = next(item for item in audit.findings if item.id == "heading-lookalike-001")
    assert finding.status == "dismissed"
    headings = next(check for check in audit.checks if check.id == "headings")
    assert finding.id not in headings.finding_ids
