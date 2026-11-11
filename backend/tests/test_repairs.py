from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from docx import Document
from docx.oxml.ns import qn

from app.audit.images import DECORATIVE_TAG, check_images
from app.audit.runner import run_audit
from app.core.config import DOCX_MIME
from app.main import app
from app.models import Audit, FixResponse, UploadResponse


@pytest.fixture
def broken_upload(client, fixture_paths):
    source = fixture_paths[0]
    response = client.post("/api/documents", files={"file": (source.name, source.read_bytes(), DOCX_MIME)})
    assert response.status_code == 201
    return UploadResponse.model_validate(response.json())


def fix(finding_id, fix_type, **payload):
    return {"finding_id": finding_id, "type": fix_type, "payload": payload}


def working_path(upload):
    store = app.state.documents
    session = store.root / str(upload.document_id)
    return store.current_state(session) / "working.docx"


def test_five_repairs_update_only_the_working_copy_and_stay_unverified(client, broken_upload, fixture_paths):
    fixes = [
        fix("title-missing", "set_title", title="Study group handout"),
        fix("language-default-missing", "set_language", lang="en-IN"),
        fix("img-001", "set_alt_text", alt_text="Attendance doubled from 12 to 24 students."),
        fix("table-001", "set_table_header"),
        fix("link-004-001", "set_link_text", new_text="Study group schedule"),
        fix("headings-missing", "set_title", title="Another title"),
    ]
    url = f"/api/documents/{broken_upload.document_id}"

    response = client.post(f"{url}/fixes", json={"fixes": fixes})

    assert response.status_code == 200
    result = FixResponse.model_validate(response.json())
    assert [item.finding_id for item in result.applied] == [item["finding_id"] for item in fixes[:5]]
    assert all(item.status == "fixed_unverified" for item in result.applied)
    assert [item.finding_id for item in result.skipped] == ["headings-missing"]
    saved = Audit.model_validate(client.get(f"{url}/audit").json())
    assert saved.audit_id == broken_upload.audit.audit_id
    assert saved.progress == broken_upload.audit.progress
    assert saved.checks == broken_upload.audit.checks
    assert {item.id for item in saved.findings if item.status == "fixed_unverified"} == {
        item.finding_id for item in result.applied
    }
    assert {item.status for item in saved.findings} == {"open", "needs_review", "fixed_unverified"}

    session = app.state.documents.root / str(broken_upload.document_id)
    assert (session / "original.docx").read_bytes() == fixture_paths[0].read_bytes()
    repaired = Document(working_path(broken_upload))
    assert repaired.core_properties.title == "Study group handout"
    link, = repaired.paragraphs[-1].hyperlinks
    assert link.text == "Study group schedule"
    assert link.url == "https://example.org/study-schedule"
    assert repaired.inline_shapes[0]._inline.docPr.get("descr") == "Attendance doubled from 12 to 24 students."
    row = repaired.tables[0].rows[0]
    assert row._tr.xpath("./w:trPr/w:tblHeader")[0].get(qn("w:val")) == "1"
    fresh_checks = run_audit(repaired, broken_upload.document_id).checks
    assert {check.id for check in fresh_checks if check.result == "passed"} == {
        "title", "language", "images", "tables", "links"
    }


def test_decorative_choice_is_persisted(client, broken_upload):
    response = client.post(
        f"/api/documents/{broken_upload.document_id}/fixes",
        json={"fixes": [fix("img-001", "set_alt_text", decorative=True)]},
    )
    assert response.status_code == 200
    assert response.json()["applied"] == [{"finding_id": "img-001", "status": "fixed_unverified"}]
    repaired = Document(working_path(broken_upload))
    properties = repaired.inline_shapes[0]._inline.docPr
    assert properties.get("descr") is None
    assert next(properties.iter(DECORATIVE_TAG)).get("val") == "1"
    assert check_images(repaired)[0].result == "passed"


def test_invalid_mismatched_and_repeat_fixes_are_skipped(client, broken_upload):
    url = f"/api/documents/{broken_upload.document_id}/fixes"
    bad_fixes = [
        fix("title-missing", "set_title", title=" "),
        fix("title-missing", "set_title", title="x" * 256),
        fix("title-missing", "set_title", title="Invalid\x00title"),
        fix("language-default-missing", "set_language", lang="not_a_tag"),
        fix("img-001", "set_alt_text", decorative=True, alt_text="Conflicting choices"),
        fix("link-004-001", "set_link_text", new_text="Click here"),
        fix("table-001", "set_title", title="Wrong target"),
        fix("table-001", "set_table_header", title="Wrong field"),
        fix("missing-finding", "set_table_header"),
    ]
    response = client.post(url, json={"fixes": bad_fixes})
    assert response.status_code == 200
    assert response.json()["applied"] == []
    assert len(response.json()["skipped"]) == len(bad_fixes)
    assert working_path(broken_upload).parent.name == str(broken_upload.document_id)

    valid = fix("title-missing", "set_title", title="Approved title")
    response = client.post(url, json={"fixes": [valid, valid]})
    assert len(response.json()["applied"]) == len(response.json()["skipped"]) == 1
    retry = client.post(url, json={"fixes": [valid]})
    assert retry.json()["applied"] == []
    assert len(retry.json()["skipped"]) == 1


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"fixes": [{}]}, "fix_invalid"),
        ({"fixes": [fix("title-missing", "set_heading")]}, "fix_not_supported"),
        ({"fixes": [fix("img-001", "set_alt_text", decorative="yes")]}, "fix_invalid"),
    ],
)
def test_malformed_fix_request_uses_repair_errors(client, broken_upload, payload, code):
    response = client.post(f"/api/documents/{broken_upload.document_id}/fixes", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_fixes_for_unknown_session_return_404(client):
    response = client.post("/api/documents/00000000-0000-0000-0000-000000000000/fixes", json={"fixes": []})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_failed_commit_leaves_working_copy_and_audit_consistent(client, broken_upload, monkeypatch):
    url = f"/api/documents/{broken_upload.document_id}"
    initial = working_path(broken_upload).read_bytes()
    payload = {"fixes": [fix("title-missing", "set_title", title="Approved title")]}
    with monkeypatch.context() as patch:
        def fail_replace(_source, _destination):
            raise OSError("Simulated state switch failure")

        patch.setattr(Path, "replace", fail_replace)
        response = client.post(f"{url}/fixes", json=payload)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "storage_failed"
    assert working_path(broken_upload).read_bytes() == initial
    assert Audit.model_validate(client.get(f"{url}/audit").json()) == broken_upload.audit
    assert client.post(f"{url}/fixes", json=payload).json()["applied"]


def test_concurrent_repairs_keep_both_updates(client, broken_upload):
    url = f"/api/documents/{broken_upload.document_id}/fixes"
    first = fix("title-missing", "set_title", title="Approved title")
    second = fix("language-default-missing", "set_language", lang="en-US")

    def apply(item):
        return client.post(url, json={"fixes": [item]})

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(apply, [first, second]))
    assert all(response.status_code == 200 and len(response.json()["applied"]) == 1 for response in responses)
    repaired = Document(working_path(broken_upload))
    audit = run_audit(repaired, broken_upload.document_id)
    assert [check.result for check in audit.checks[:2]] == ["passed", "passed"]
