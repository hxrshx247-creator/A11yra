from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier, Event
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import select

from app.core.config import DOCX_MIME, MAX_EXPANDED_BYTES, MAX_PACKAGE_PARTS, MAX_UPLOAD_BYTES
from app.main import app
from app.product import integration, plans
from app.product.security import digest
from app.product.tables import ApiKey, UsageEvent
from test_product import PASSWORD, workspace

AUDIT = "/api/public/v1/audit"


@pytest.fixture
def key(client):
    owner = workspace(client)
    base = f"/api/workspaces/{owner}"
    assert client.post(f"{base}/billing/demo", json={"plan": "institution"}).status_code == 204
    created = client.post(f"{base}/keys", json={"name": "Audit test"}).json()
    return base, created


def audit(client, created, contents, name="test.docx", mime=DOCX_MIME):
    headers = {"Authorization": f"Bearer {created['key']}"} if created else {}
    return client.post(AUDIT, headers=headers, files={"file": (name, contents, mime)})


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def package_case(case):
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as package:
        package.writestr("word/document.xml", "<document/>")
        types = "macroEnabled" if case == "macro type" else "<Types/>"
        package.writestr("[Content_Types].xml", types)
        if case == "expanded size":
            with package.open("fixture.txt", "w") as entry:
                chunk = b"x" * 1_000_000
                for _ in range(MAX_EXPANDED_BYTES // len(chunk) + 1):
                    entry.write(chunk)
        elif case == "entry count":
            for index in range(MAX_PACKAGE_PARTS):
                package.writestr(f"fixture/{index}.txt", "")
        elif case == "macro":
            package.writestr("word/vbaProject.bin", "inert fixture")
        elif case == "executable":
            package.writestr("fixture/attachment.exe", "inert fixture")
    return output.getvalue()


@pytest.mark.parametrize("case", ["expanded size", "entry count", "macro", "macro type", "executable"])
def test_public_api_rejects_invalid_packages(client, key, case):
    assert_error(audit(client, key[1], package_case(case)), 422, "corrupt_docx")


def test_public_api_auth_size_and_file_type(client, key, fixture_paths):
    source = fixture_paths[1].read_bytes()
    assert_error(audit(client, None, source), 401, "invalid_api_key")
    assert_error(audit(client, {"key": "a11yra_" + "A" * 43}, source), 401, "invalid_api_key")
    assert_error(audit(client, key[1], source, mime="text/plain"), 415, "invalid_file_type")
    assert_error(audit(client, key[1], b"invalid ZIP"), 422, "corrupt_docx")
    assert_error(audit(client, key[1], b"x" * (MAX_UPLOAD_BYTES + 1)), 413, "file_too_large")
    assert_error(audit(client, key[1], b"x" * (MAX_UPLOAD_BYTES + 100_000)), 413, "file_too_large")


def test_public_key_hash_visibility_rate_limit_and_revocation(client, key, fixture_paths):
    base, created = key
    with app.state.sessions() as db:
        row = db.get(ApiKey, created["id"])
        assert row.digest == digest(created["key"].removeprefix("a11yra_"))
    listing = client.get(f"{base}/keys")
    assert created["key"] not in listing.text and "digest" not in listing.json()[0]
    for _ in range(20):
        assert_error(audit(client, created, b"invalid ZIP"), 422, "corrupt_docx")
    assert_error(audit(client, created, fixture_paths[1].read_bytes()), 429, "rate_limit")
    other = client.post(f"{base}/keys", json={"name": "Second key"}).json()
    assert audit(client, other, fixture_paths[1].read_bytes()).status_code == 200
    assert client.delete(f"{base}/keys/{other['id']}").status_code == 204
    assert_error(audit(client, other, fixture_paths[1].read_bytes()), 401, "invalid_api_key")


def test_public_api_plan_quota(client, key, fixture_paths, monkeypatch):
    from dataclasses import replace

    monkeypatch.setitem(plans.PLANS, "institution", replace(plans.PLANS["institution"], documents_per_month=1))
    source = fixture_paths[1].read_bytes()
    barrier = Barrier(2, timeout=5)
    original = integration.run_audit

    def simultaneous(*args):
        barrier.wait()
        return original(*args)

    monkeypatch.setattr(integration, "run_audit", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(audit, client, key[1], source)
        second = workers.submit(audit, client, key[1], source)
        accepted, rejected = sorted((first.result(), second.result()), key=lambda result: result.status_code)
    assert accepted.status_code == 200
    assert_error(rejected, 429, "plan_limit")


def test_public_api_times_out_without_recording_usage(client, key, fixture_paths, monkeypatch):
    entered, resume, finished = Event(), Event(), Event()
    original = integration.run_audit
    execute = integration.execute_public_audit

    def slow(*args):
        entered.set()
        assert resume.wait(timeout=5)
        return original(*args)

    def track(*args):
        try:
            return execute(*args)
        finally:
            finished.set()

    monkeypatch.setattr(integration, "run_audit", slow)
    monkeypatch.setattr(integration, "execute_public_audit", track)
    monkeypatch.setattr(app.state, "public_audit_timeout", 0.5)
    try:
        assert_error(audit(client, key[1], fixture_paths[1].read_bytes()), 408, "request_timeout")
        assert entered.is_set()
    finally:
        resume.set()
    assert finished.wait(timeout=5)
    with app.state.sessions() as db:
        assert db.scalar(select(UsageEvent.id)) is None
        assert db.get(ApiKey, key[1]["id"]).last_used_at is None


def test_signup_and_reset_requests_are_generic_and_rate_limited(client):
    signup = "/api/auth/signup"
    known, unknown = "teacher@example.test", "new@example.test"
    known_signup = client.post(signup, json={"email": known, "password": PASSWORD})
    unknown_signup = client.post(signup, json={"email": unknown, "password": PASSWORD})
    assert known_signup.status_code == unknown_signup.status_code == 202
    assert known_signup.json() == unknown_signup.json()
    for _ in range(2):
        assert client.post(signup, json={"email": known, "password": PASSWORD}).status_code == 202
    assert_error(client.post(signup, json={"email": known, "password": PASSWORD}), 429, "rate_limit")

    forgot = "/api/auth/forgot"
    known_reset = client.post(forgot, json={"email": known})
    unknown_reset = client.post(forgot, json={"email": "unknown@example.test"})
    assert known_reset.status_code == unknown_reset.status_code == 202
    assert known_reset.json() == unknown_reset.json()
    for _ in range(2):
        assert client.post(forgot, json={"email": known}).status_code == 202
    assert_error(client.post(forgot, json={"email": known}), 429, "rate_limit")


@pytest.mark.parametrize("endpoint", ["verify", "reset"])
def test_invalid_account_tokens_are_generic_and_rate_limited(client, endpoint):
    path = f"/api/auth/{endpoint}"
    first_error = None
    for index in range(10):
        body = {"token": str(index) * 43}
        if endpoint == "reset":
            body["password"] = PASSWORD
        response = client.post(path, json=body)
        assert_error(response, 400, "link_invalid")
        if first_error is None:
            first_error = response.json()
        assert response.json() == first_error
    assert_error(client.post(path, json=body), 429, "rate_limit")
