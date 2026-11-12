import os
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.main import app
from app.product.db import build_engine
from scripts.make_fixtures import make_fixtures


@pytest.fixture(scope="session")
def fixture_paths(tmp_path_factory):
    return make_fixtures(tmp_path_factory.mktemp("handouts"))


@pytest.fixture
def broken_doc(fixture_paths):
    return Document(fixture_paths[0])


@pytest.fixture
def clean_doc(fixture_paths):
    return Document(fixture_paths[1])


@pytest.fixture
def test_database_url(tmp_path):
    configured = os.getenv("A11YRA_TEST_POSTGRES_URL")
    if not configured:
        yield f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
        return
    url = make_url(configured)
    if url.get_backend_name() != "postgresql":
        raise ValueError("A11YRA_TEST_POSTGRES_URL must name a disposable Postgres database.")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    schema = f"a11yra_test_{uuid4().hex}"
    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            options = f"{url.query.get('options', '')} -csearch_path={schema}".strip()
            yield url.update_query_dict({"options": options}).render_as_string(hide_password=False)
        finally:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    finally:
        engine.dispose()


@pytest.fixture
def anonymous(tmp_path, monkeypatch, test_database_url):
    monkeypatch.setenv("A11YRA_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("A11YRA_DATA_DIR", str(tmp_path / "data"))
    with TestClient(app) as test_client:
        yield test_client


def sign_in(client, email="teacher@example.test", password="a test password 123"):
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf
    body = {"email": email, "password": password}
    assert client.post("/api/auth/signup", json=body).status_code == 202
    response = client.post("/api/auth/login", json=body)
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = client.cookies["a11yra_csrf"]
    return response.json()


@pytest.fixture
def client(anonymous):
    sign_in(anonymous)
    return anonymous
