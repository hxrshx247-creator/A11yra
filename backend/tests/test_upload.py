from io import BytesIO
from os import utime
from time import time
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document

from app.core.config import DOCX_MIME, MAX_UPLOAD_BYTES, SESSION_TTL_SECONDS
from app.main import app
from app.models import UploadResponse


@pytest.fixture
def docx_bytes():
    buffer = BytesIO()
    document = Document()
    document.add_paragraph("Example handout")
    document.save(buffer)
    return buffer.getvalue()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_valid_upload_stores_private_copies_and_audit(client, docx_bytes):
    root = app.state.documents.root
    response = client.post(
        "/api/documents", files={"file": (r"..\Handout.DOCX", docx_bytes, DOCX_MIME)}
    )
    assert response.status_code == 201
    upload = UploadResponse.model_validate(response.json())
    assert upload.filename == "Handout.DOCX"
    assert upload.audit.document_id == upload.document_id
    assert [check.id for check in upload.audit.checks] == [
        "title", "language", "headings", "images", "tables", "links",
    ]
    assert [check.result for check in upload.audit.checks] == [
        "issues", "passed", "issues", "not_evaluated", "not_evaluated", "not_evaluated",
    ]
    assert upload.audit.progress.model_dump() == {"passed": 1, "evaluated": 3, "percent": 33}
    session = root / str(upload.document_id)
    assert (session / "original.docx").read_bytes() == docx_bytes
    assert (session / "working.docx").read_bytes() == docx_bytes
    assert (session / "audit.json").read_text(encoding="utf-8") == upload.audit.model_dump_json()
    assert root.exists()


@pytest.mark.parametrize(
    ("name", "mime"),
    [("notes.txt", DOCX_MIME), ("notes.docx", "text/plain"), (".docx", DOCX_MIME)],
)
def test_rejects_wrong_extension_or_mime(client, docx_bytes, name, mime):
    response = client.post("/api/documents", files={"file": (name, docx_bytes, mime)})
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "invalid_file_type"
    assert list(app.state.documents.root.iterdir()) == []


def test_requires_file_field(client):
    response = client.post("/api/documents")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_file_type"


def test_rejects_file_above_size_limit(client):
    response = client.post(
        "/api/documents", files={"file": ("large.docx", b"x" * (MAX_UPLOAD_BYTES + 1), DOCX_MIME)}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert list(app.state.documents.root.iterdir()) == []


def test_rejects_oversized_multipart_request(client):
    response = client.post(
        "/api/documents", files={"file": ("large.docx", b"x" * (MAX_UPLOAD_BYTES + 70_000), DOCX_MIME)}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


@pytest.mark.parametrize("part", [None, "notes.txt", "word/document.xml"])
def test_rejects_invalid_docx_packages(client, part):
    if part is None:
        contents = b"plain text"
    else:
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as package:
            package.writestr(part, "<invalid/>")
        contents = buffer.getvalue()

    response = client.post("/api/documents", files={"file": ("notes.docx", contents, DOCX_MIME)})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "corrupt_docx"
    assert list(app.state.documents.root.iterdir()) == []


def test_expiry_removes_old_session_only(client, docx_bytes):
    store = app.state.documents
    ids = [
        client.post(
            "/api/documents", files={"file": ("notes.docx", docx_bytes, DOCX_MIME)}
        ).json()["document_id"]
        for _ in range(2)
    ]
    old, current = (store.root / document_id for document_id in ids)
    expired_at = time() - SESSION_TTL_SECONDS - 1
    utime(old / "original.docx", (expired_at, expired_at))
    store.expire_old_sessions()
    assert not old.exists()
    assert current.exists()
