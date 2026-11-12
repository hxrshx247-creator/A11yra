from datetime import datetime, timedelta
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.core.config import DOCX_MIME
from app.main import app
from app.product import documents
from app.product.security import TOKEN_PATTERN, digest
from app.product.tables import Membership, ReaderShare, User
from conftest import sign_in
from test_product import sample, workspace


def test_reader_expiry_revocation_and_token_storage(client, monkeypatch):
    clock = datetime(2030, 1, 1, 12)
    doc = sample(client)["document_id"]
    endpoint = f"/api/documents/{doc}/shares"
    first = client.post(endpoint, json={"days": 1}).json()
    second = client.post(endpoint, json={"days": 1}).json()
    path = urlsplit(first["url"]).path
    revoked_path = urlsplit(second["url"]).path
    token = path.rsplit("/", 1)[-1]
    assert TOKEN_PATTERN.fullmatch(token)
    assert revoked_path != path
    with app.state.sessions.begin() as db:
        share = db.get(ReaderShare, first["id"])
        assert share.digest == digest(token)
        share.expires_at = clock
        db.get(ReaderShare, second["id"]).expires_at = clock + timedelta(days=1)

    monkeypatch.setattr(documents, "now", lambda: clock - timedelta(microseconds=1))
    browser = TestClient(app)
    opened = browser.get(path)
    assert opened.status_code == 200
    assert opened.headers["cache-control"] == "private, no-store"
    assert browser.get(revoked_path).status_code == 200
    assert client.delete(f"{endpoint}/{second['id']}").status_code == 204
    monkeypatch.setattr(documents, "now", lambda: clock)
    unknown = browser.get("/r/" + "A" * 43)
    for response in (browser.get(path), browser.get(revoked_path), browser.get("/r/invalid"), unknown):
        assert response.status_code == 404
        assert response.content == unknown.content
        assert response.headers["cache-control"] == "private, no-store"
    assert "etag" not in opened.headers and "last-modified" not in opened.headers


@pytest.mark.parametrize("role", ["outsider", "viewer", "editor", "owner"])
def test_workspace_route_matrix(client, fixture_paths, role):
    owner_workspace = workspace(client)
    profile = client.get("/api/auth/me").json()
    owner_id = profile["id"]
    base = f"/api/workspaces/{owner_workspace}"
    doc = sample(client)["document_id"]
    resource = f"/api/documents/{doc}"
    share = client.post(f"{resource}/shares", json={"days": 1}).json()["id"]
    assert client.post(f"{base}/billing/demo", json={"plan": "institution"}).status_code == 204
    key = client.post(f"{base}/keys", json={"name": "Owner key"}).json()["id"]

    colleague = TestClient(app)
    other = sign_in(colleague, "colleague@example.test")
    with app.state.sessions.begin() as db:
        db.get(User, owner_id).email_verified = True
        if role != "outsider":
            db.add(Membership(workspace_id=owner_workspace, user_id=other["id"],
                              role=role if role != "owner" else "viewer"))
    actor = client if role == "owner" else colleague
    source = fixture_paths[1]
    upload = {"files": {"file": ("example.docx", source.read_bytes(), DOCX_MIME)},
              "headers": {"X-Workspace-Id": owner_workspace}}
    routes = [
        ("GET", f"{base}/documents", "viewer", 200, {}),
        ("GET", f"{base}/usage", "viewer", 200, {}),
        ("GET", f"{resource}/audit", "viewer", 200, {}),
        ("GET", f"{resource}/history", "viewer", 200, {}),
        ("GET", f"{resource}/export/docx", "viewer", 200, {}),
        ("GET", f"{resource}/export/html", "viewer", 200, {}),
        ("GET", f"{resource}/export/html?offline=true", "viewer", 200, {}),
        ("POST", "/api/documents", "editor", 201, upload),
        ("POST", "/api/documents/sample", "editor", 201, {"headers": upload["headers"]}),
        ("POST", f"{resource}/fixes", "editor", 200, {"json": {"fixes": []}}),
        ("POST", f"{resource}/reaudit", "editor", 200, {}),
        ("GET", f"{resource}/shares", "editor", 200, {}),
        ("POST", f"{resource}/shares", "editor", 201, {"json": {"days": 1}}),
        ("DELETE", f"{resource}/shares/{share}", "editor", 204, {}),
        ("GET", f"{base}/activity", "editor", 200, {}),
        ("GET", f"{base}/activity?format=csv", "editor", 200, {}),
        ("GET", f"{base}/dashboard", "owner", 200, {}),
        ("GET", f"{base}/dashboard?format=csv", "owner", 200, {}),
        ("GET", f"{base}/members", "owner", 200, {}),
        ("POST", f"{base}/invites", "owner", 202, {"json": {"email": "invitee@example.test", "role": "viewer"}}),
        ("PATCH", f"{base}/members/{other['id']}", "owner", 204, {"json": {"role": "editor"}}),
        ("GET", f"{base}/keys", "owner", 200, {}),
        ("POST", f"{base}/keys", "owner", 201, {"json": {"name": "New key"}}),
        ("DELETE", f"{base}/keys/{key}", "owner", 204, {}),
        ("POST", f"{base}/billing/checkout", "owner", 409, {"json": {"plan": "institution"}}),
        ("POST", f"{base}/billing/demo", "owner", 204, {"json": {"plan": "institution"}}),
        ("DELETE", resource, "editor", 204, {}),
    ]
    ranks = {"outsider": -1, "viewer": 0, "editor": 1, "owner": 2}
    for method, path, minimum, allowed, kwargs in routes:
        expected = allowed if ranks[role] >= ranks[minimum] else 404 if role == "outsider" else 403
        response = actor.request(method, path, **kwargs)
        assert response.status_code == expected, (method, path, response.status_code)
