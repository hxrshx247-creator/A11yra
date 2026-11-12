from datetime import timedelta
from io import BytesIO
from urllib.parse import urlsplit

import pytest
from docx import Document as WordDocument
from sqlalchemy import select

from app.core.config import DOCX_MIME
from app.main import app
from app.product.db import now
from app.product.retention import cleanup
from app.product.tables import (
    AccountToken, ApiKey, AuditLog, AuditRecord, Document, ExportRecord, FixRecord,
    Membership, ReaderShare, Session, Subscription, UsageEvent, User, Workspace,
)
from test_product import PASSWORD


@pytest.mark.parametrize("mode", ["expiry", "document", "account"])
def test_data_lifecycle_removes_files_and_rows_without_logging_word_text(client, capsys, caplog, mode):
    sentinel = f"A11yra private document text sentinel {mode} 492851"
    word = WordDocument()
    word.add_heading("Privacy fixture", level=1)
    word.add_paragraph(sentinel)
    content = BytesIO()
    word.save(content)
    profile = client.get("/api/auth/me").json()
    workspace_id = profile["workspaces"][0]["id"]
    user_id = profile["id"]
    workspace_path = f"/api/workspaces/{workspace_id}"

    uploaded = client.post("/api/documents", files={"file": ("privacy.docx", content.getvalue(), DOCX_MIME)})
    assert uploaded.status_code == 201
    doc = uploaded.json()["document_id"]
    base = f"/api/documents/{doc}"
    title = next(f for f in uploaded.json()["audit"]["findings"] if f["check_id"] == "title")
    fixed = client.post(f"{base}/fixes", json={"fixes": [
        {"finding_id": title["id"], "type": "set_title", "payload": {"title": "Privacy fixture"}},
    ]})
    assert len(fixed.json()["applied"]) == 1
    assert client.post(f"{base}/reaudit").status_code == 200
    assert client.get(f"{base}/export/docx").status_code == 200
    assert client.get(f"{base}/export/html?offline=true").status_code == 200
    share = client.post(f"{base}/shares", json={"days": 1}).json()
    public_path = urlsplit(share["url"]).path
    assert sentinel in client.get(public_path).text
    doc_path = app.state.documents.root / doc
    share_path = app.state.shares_root / f"{share['id']}.html"
    assert doc_path.exists() and share_path.exists()

    assert client.post(f"{workspace_path}/billing/demo", json={"plan": "institution"}).status_code == 204
    key = client.post(f"{workspace_path}/keys", json={"name": "Privacy fixture"}).json()["id"]
    children = (AuditRecord, FixRecord, ExportRecord, ReaderShare)
    with app.state.sessions() as db:
        for table in children:
            assert db.scalar(select(table.id).where(table.document_id == doc))

    if mode == "expiry":
        with app.state.sessions.begin() as db:
            db.get(Document, doc).expires_at = now() - timedelta(seconds=1)
        cleanup(app.state)
        assert not doc_path.exists() and share_path.exists()
        assert client.get(public_path).status_code == 200
        assert client.get(f"{base}/history").status_code == 200
        with app.state.sessions.begin() as db:
            db.get(ReaderShare, share["id"]).expires_at = now() - timedelta(seconds=1)
        cleanup(app.state)
        assert not share_path.exists()
        with app.state.sessions.begin() as db:
            db.get(Document, doc).history_until = now() - timedelta(seconds=1)
        cleanup(app.state)
    elif mode == "document":
        assert client.delete(base).status_code == 204
    else:
        assert client.request("DELETE", "/api/auth/account", json={"confirm": True, "password": PASSWORD}).status_code == 204

    assert not doc_path.exists() and not share_path.exists()
    assert client.get(public_path).status_code == 404
    with app.state.sessions() as db:
        assert db.get(Document, doc) is None
        for table in children:
            assert db.scalar(select(table.id).where(table.document_id == doc)) is None
        if mode == "account":
            assert db.get(ApiKey, key) is None
            assert db.get(Workspace, workspace_id) is None
            assert db.get(Subscription, workspace_id) is None
            assert db.get(User, user_id) is None
            for table in (Membership, Session, AccountToken):
                assert db.scalar(select(table.user_id).where(table.user_id == user_id)) is None
            assert db.scalar(select(UsageEvent.id).where(UsageEvent.workspace_id == workspace_id)) is None
            assert db.scalar(select(AuditLog.id).where(AuditLog.action == "account_deleted"))
            assert db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id == user_id)) is None
            assert db.scalar(select(AuditLog.id).where(AuditLog.target_id == user_id)) is None
        else:
            assert db.get(ApiKey, key) is not None
            assert db.scalar(select(UsageEvent.id).where(UsageEvent.workspace_id == workspace_id))
        assert all(sentinel not in str(entry.metadata_json) for entry in db.scalars(select(AuditLog)))
    output = capsys.readouterr()
    logged = output.out + output.err + caplog.text
    assert '"route": "/api/documents"' in logged
    assert sentinel not in logged
