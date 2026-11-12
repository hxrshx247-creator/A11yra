from io import BytesIO
from zipfile import ZipFile

import pytest
from bs4 import BeautifulSoup

from app.core.config import DOCX_MIME
from app.main import app
from scripts.make_fixtures import make_syllabus


@pytest.mark.parametrize("offline", [True, False])
def test_syllabus_repair_verification_and_learner_export(client, tmp_path, offline):
    syllabus = make_syllabus(tmp_path)
    upload = client.post(
        "/api/documents", files={"file": (syllabus.name, syllabus.read_bytes(), DOCX_MIME)}
    )
    assert upload.status_code == 201
    body = upload.json()
    assert body["audit"]["progress"]["passed"] == 5
    assert [item["id"] for item in body["audit"]["findings"]] == ["img-001"]
    base = f"/api/documents/{body['document_id']}"
    response = client.post(f"{base}/fixes", json={"fixes": [
        {"finding_id": "img-001", "type": "set_alt_text", "payload": {"alt_text": "Attendance doubled from 12 to 24 students."}},
    ]})
    assert response.json()["applied"][0]["status"] == "fixed_unverified"
    export_url = f"{base}/export/html?offline={str(offline).lower()}"
    assert client.get(export_url).status_code == 409
    verified = client.post(f"{base}/reaudit").json()
    assert verified["diff"]["verified_fixed"] == ["img-001"]
    assert verified["diff"]["progress_after"]["passed"] == 6

    # Each export uses the same verified document and leaves it available for the next format.
    assert client.get(f"{base}/export/docx").status_code == 200
    other_format = f"{base}/export/html?offline={str(not offline).lower()}"
    assert client.get(other_format).status_code == 200
    result = client.get(export_url)

    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    if offline:
        assert result.headers["content-type"].startswith("text/html")
        assert "a11yra-reader.html" in result.headers["content-disposition"]
        page = BeautifulSoup(result.content, "html.parser")
        assert page.img["src"].startswith("data:image/png;base64,")
        assert page.script.get("src") is None
        assert page.style is not None
    else:
        assert result.headers["content-type"] == "application/zip"
        assert "a11yra-reader.zip" in result.headers["content-disposition"]
        with ZipFile(BytesIO(result.content)) as archive:
            page = BeautifulSoup(archive.read("index.html"), "html.parser")
            assert set(archive.namelist()) == {"index.html", "reader.js", "reader.css", page.img["src"]}
            assert archive.read(page.img["src"]).startswith(b"\x89PNG")
        assert page.script["src"] == "reader.js"
        assert page.find("link", rel="stylesheet")["href"] == "reader.css"
    assert page.select_one("#ruler-enabled") is not None
    assert page.title.get_text() == "Study Group Syllabus"
    assert page.img["alt"] == "Attendance doubled from 12 to 24 students."
    assert page.table.caption.get_text() == "Study sessions and rooms"
    assert client.get(f"{base}/audit").status_code == 200
    assert (app.state.documents.root / body["document_id"]).exists()
