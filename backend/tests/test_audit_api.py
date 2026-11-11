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
    assert all("preview" not in finding for finding in response.json()["findings"])
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
