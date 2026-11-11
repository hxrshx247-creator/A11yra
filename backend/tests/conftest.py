import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
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
def client():
    with TestClient(app) as test_client:
        yield test_client
