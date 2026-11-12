from app.main import app


def start_demo(client):
    client.headers["X-CSRF-Token"] = client.get("/api/auth/csrf").json()["csrf_token"]
    response = client.post("/api/auth/demo-session")
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = client.cookies["a11yra_csrf"]
    return response.json()


def test_demo_sessions_are_isolated_and_reused(anonymous, monkeypatch):
    assert anonymous.post("/api/auth/demo-session").status_code == 404
    monkeypatch.setattr(app.state, "demo_mode", True)
    assert anonymous.post("/api/auth/demo-session").status_code == 403

    first = start_demo(anonymous)
    assert start_demo(anonymous)["id"] == first["id"]
    upload = anonymous.post("/api/documents/sample?kind=lecture")
    assert upload.status_code == 201
    audit = f"/api/documents/{upload.json()['document_id']}/audit"
    assert anonymous.get(audit).status_code == 200

    anonymous.cookies.clear()
    assert start_demo(anonymous)["id"] != first["id"]
    assert anonymous.get(audit).status_code == 404
