import hashlib
import hmac
import json
import re
from datetime import timedelta
from pathlib import Path
from time import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import DOCX_MIME
from app.main import app
from app.product.db import now
from app.product.retention import cleanup
from app.product.tables import AuditLog, Document, User
from conftest import sign_in

PASSWORD = "a test password 123"


def sample(client):
    response = client.post("/api/documents/sample")
    assert response.status_code == 201, response.text
    return response.json()


def workspace(client):
    return client.get("/api/auth/me").json()["workspaces"][0]["id"]


def test_auth_csrf_rotation_and_logout(anonymous):
    assert anonymous.get("/api/auth/me").status_code == 401
    assert anonymous.post("/api/auth/signup", json={"email": "teacher@example.test", "password": PASSWORD}).status_code == 403
    sign_in(anonymous)
    old = anonymous.cookies["a11yra_refresh"]
    assert anonymous.post("/api/auth/refresh", headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert anonymous.post("/api/auth/refresh").status_code == 204
    assert anonymous.cookies["a11yra_refresh"] != old
    replay = TestClient(app)
    replay.cookies.set("a11yra_refresh", old)
    replay.cookies.set("a11yra_csrf", anonymous.cookies["a11yra_csrf"])
    assert replay.post("/api/auth/refresh", headers={"X-CSRF-Token": anonymous.cookies["a11yra_csrf"]}).status_code == 401
    assert anonymous.post("/api/auth/logout").status_code == 204
    assert anonymous.get("/api/auth/me").status_code == 401


def test_reset_link_is_single_use_and_revokes_sessions(client, capsys):
    body = {"email": "teacher@example.test"}
    assert client.post("/api/auth/forgot", json=body).status_code == 202
    raw = re.findall(r"/account/reset#token=([\w-]{43})", capsys.readouterr().out)[-1]
    reset = {"token": raw, "password": "updated password 123"}
    assert client.post("/api/auth/reset", json=reset).status_code == 204
    assert client.post("/api/auth/reset", json=reset).status_code == 400
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={**body, "password": reset["password"]}).status_code == 200


def test_generic_login_and_backoff(client):
    assert client.post("/api/auth/logout").status_code == 204
    client.headers["X-CSRF-Token"] = client.get("/api/auth/csrf").json()["csrf_token"]
    def login(email, password):
        return client.post("/api/auth/login", json={"email": email, "password": password})
    missing = login("missing@example.test", "wrong").json()
    for _ in range(5):
        denied = login("teacher@example.test", "wrong")
        assert denied.status_code == 401
        assert denied.json() == missing
    assert login("teacher@example.test", PASSWORD).status_code == 401
    for _ in range(21):
        response = login("missing@example.test", "wrong")
    assert response.status_code == 429


def test_workspace_isolation_invite_and_role_change(client, capsys):
    owner_workspace = workspace(client)
    document = sample(client)["document_id"]
    other = TestClient(app)
    sign_in(other, "colleague@example.test")
    for suffix in ("audit", "history", "export/docx"):
        assert other.get(f"/api/documents/{document}/{suffix}").status_code == 404
    assert other.get(f"/api/workspaces/{owner_workspace}/activity").status_code == 404
    with app.state.sessions.begin() as db:
        for user in db.scalars(select(User)):
            user.email_verified = True
    base = f"/api/workspaces/{owner_workspace}"
    assert client.post(f"{base}/invites", json={"email": "colleague@example.test", "role": "viewer"}).status_code == 202
    raw = re.findall(r"/account/invite#token=([\w-]{43})", capsys.readouterr().out)[-1]
    assert other.post("/api/invites/accept", json={"token": raw}).status_code == 200
    assert other.get(f"/api/documents/{document}/audit").status_code == 200
    assert other.post(f"/api/documents/{document}/reaudit").status_code == 403
    assert other.get(f"{base}/activity").status_code == 403
    other_id = other.get("/api/auth/me").json()["id"]
    assert client.patch(f"{base}/members/{other_id}", json={"role": "editor"}).status_code == 204
    assert other.post(f"/api/documents/{document}/reaudit").status_code == 200
    assert other.get(f"{base}/dashboard").status_code == 403
    rows = other.get(f"{base}/activity", params={"action": "role_changed"}).json()
    assert [row["action"] for row in rows] == ["role_changed"]
    assert client.patch(f"{base}/activity/{rows[0]['target_id']}", json={}).status_code == 404
    assert client.delete(f"{base}/activity").status_code == 405


def test_verified_history_public_reader_and_retention(client):
    upload = sample(client)
    assert upload["audit"]["progress"]["passed"] == 2
    id = upload["document_id"]
    base = f"/api/documents/{id}"
    repairs = {
        "title": ("set_title", {"title": "Study Group Syllabus"}),
        "language": ("set_language", {"lang": "en-IN"}),
        "images": ("set_alt_text", {"alt_text": "Attendance doubled from 12 to 24 students."}),
        "links": ("set_link_text", {"new_text": "Weekly study group schedule"}),
    }
    fixes = [{"finding_id": row["id"], "type": repairs[row["check_id"]][0], "payload": repairs[row["check_id"]][1]}
             for row in upload["audit"]["findings"]]
    assert client.post(f"{base}/fixes", json={"fixes": fixes}).status_code == 200
    assert client.post(f"{base}/shares", json={"days": 7}).status_code == 409
    audit = client.post(f"{base}/reaudit").json()
    assert audit["diff"]["progress_after"]["passed"] == 6
    assert len(audit["diff"]["verified_fixed"]) == 4
    share = client.post(f"{base}/shares", json={"days": 7}).json()
    path = urlsplit(share["url"]).path
    assert TestClient(app).get(path).status_code == 200
    assert client.get(f"{base}/export/docx").status_code == 200
    with app.state.sessions.begin() as db:
        db.get(Document, id).expires_at = now() - timedelta(seconds=1)
    cleanup(app.state)
    assert not (app.state.documents.root / id).exists()
    assert client.get(f"{base}/audit").status_code == 404
    assert [item["progress"]["passed"] for item in client.get(f"{base}/history").json()["versions"]] == [2, 6]
    assert TestClient(app).get(path).status_code == 200
    assert client.delete(f"{base}/shares/{share['id']}").status_code == 204
    assert TestClient(app).get(path).status_code == 404
    assert client.delete(base).status_code == 204
    assert client.get(f"{base}/history").status_code == 404
    with app.state.sessions() as db:
        actions = list(db.scalars(select(AuditLog.action)))
    assert {"document_expired", "document_deleted", "fix_applied", "reaudit", "export_downloaded"} <= set(actions)


def test_quota_keys_account_export_and_delete(client):
    owner = workspace(client)
    base = f"/api/workspaces/{owner}"
    uploads = [sample(client) for _ in range(5)]
    response = client.post("/api/documents/sample")
    assert response.status_code == 429 and response.json()["error"]["code"] == "plan_limit"
    assert client.post(f"{base}/keys", json={"name": "test"}).status_code == 403
    assert client.post(f"{base}/billing/demo", json={"plan": "institution"}).status_code == 204
    created = client.post(f"{base}/keys", json={"name": "test"}).json()
    keys = client.get(f"{base}/keys").json()
    assert keys[0]["id"] == created["id"] and "key" not in keys[0]
    file = (Path(__file__).resolve().parents[1] / "fixtures" / "pilot-syllabus.docx").read_bytes()
    endpoint = "/api/public/v1/audit"
    headers = {"Authorization": f"Bearer {created['key']}"}
    files = {"file": ("syllabus.docx", file, DOCX_MIME)}
    assert client.post(endpoint, headers=headers, files=files).json()["progress"]["passed"] == 2
    assert client.get(f"{base}/usage").json()["documents_used"] == 6
    assert client.delete(f"{base}/keys/{created['id']}").status_code == 204
    assert client.post(endpoint, headers=headers, files=files).status_code == 401
    assert len(client.get("/api/auth/data").json()["documents"]) == len(uploads)
    assert client.request("DELETE", "/api/auth/account", json={"confirm": True, "password": PASSWORD}).status_code == 204
    assert not list(app.state.documents.root.iterdir())
    assert client.get("/api/auth/me").status_code == 401
    with app.state.sessions() as db:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "account_deleted"))


def test_signed_stripe_test_event_changes_workspace_plan(client, monkeypatch):
    owner = workspace(client)
    billing = app.state.billing
    secret = "test-webhook-secret"
    monkeypatch.setattr(billing, "enabled", True)
    monkeypatch.setattr(billing, "webhook_secret", secret)
    monkeypatch.setitem(billing.prices, "institution", "price_fixture")
    subscription = SimpleNamespace(
        livemode=False, status="active",
        items=SimpleNamespace(data=[SimpleNamespace(price=SimpleNamespace(id="price_fixture"))]),
    )
    monkeypatch.setattr(billing, "client", SimpleNamespace(
        v1=SimpleNamespace(subscriptions=SimpleNamespace(retrieve=lambda _: subscription)),
    ))
    timestamp = int(time())
    event = {
        "id": "evt_fixture", "object": "event", "created": timestamp, "livemode": False,
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_fixture", "object": "subscription", "metadata": {"workspace_id": owner}}},
    }
    payload = json.dumps(event).encode()
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    endpoint = "/api/billing/webhook"
    assert client.post(endpoint, content=payload, headers={"stripe-signature": "invalid"}).status_code == 400
    assert client.post(endpoint, content=payload, headers={
        "stripe-signature": f"t={timestamp},v1={signature}",
    }).status_code == 204
    assert client.get(f"/api/workspaces/{owner}/usage").json()["plan"]["name"] == "Institution"
