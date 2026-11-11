import pytest

from app.core.config import DOCX_MIME
from app.main import app


@pytest.fixture
def upload_url(client, fixture_paths):
    source = fixture_paths[0]
    upload = client.post("/api/documents", files={"file": (source.name, source.read_bytes(), DOCX_MIME)})
    assert upload.status_code == 201
    return f"/api/documents/{upload.json()['document_id']}"


def test_export_rejects_unverified_fix_without_deleting_session(client, upload_url):
    response = client.post(f"{upload_url}/fixes", json={"fixes": [
        {"finding_id": "title-missing", "type": "set_title", "payload": {"title": "Study group handout"}},
    ]})
    assert len(response.json()["applied"]) == 1
    download = client.get(f"{upload_url}/export/docx")
    assert download.status_code == 409
    assert download.json()["error"]["code"] == "export_failed"
    assert client.get(f"{upload_url}/audit").status_code == 200


def test_invalid_working_copy_cannot_be_downloaded(client, upload_url):
    document_id = upload_url.rsplit("/", 1)[1]
    working = app.state.documents.root / document_id / "working.docx"
    working.write_bytes(b"Invalid Word package")

    download = client.get(f"{upload_url}/export/docx")

    assert download.status_code == 500
    assert download.json()["error"]["code"] == "export_failed"
    assert client.get(f"{upload_url}/audit").status_code == 200


def test_delete_removes_upload_without_downloading(client, upload_url):
    response = client.delete(upload_url)
    assert response.status_code == 204
    assert response.content == b""
    assert not list(app.state.documents.root.iterdir())
    assert client.get(f"{upload_url}/export/docx").status_code == 404
    assert client.delete(upload_url).json()["error"]["code"] == "document_not_found"
