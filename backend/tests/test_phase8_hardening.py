"""Phase 8: security, honesty, and demo-hardening checks."""

import os

import pytest

from app.document_processing.intake import LocalIntakeModule
from tests.conftest import auth_headers


def test_health_exposes_limitations_not_secrets(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "limitations" in body
    assert any("authenticity" in (x or "").lower() for x in body["limitations"])
    blob = str(body).lower()
    assert "api_key" not in blob
    assert "password" not in blob


def test_path_traversal_filename_sanitized(client):
    app = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    ).json()
    files = {"file": ("../../etc/passwd.pdf", b"%PDF-1.4 traversal", "application/pdf")}
    data = {"requirement_code": "AFFIDAVIT"}
    res = client.post(
        f"/api/v1/applications/{app['id']}/documents",
        headers=auth_headers("applicant"),
        files=files,
        data=data,
    )
    assert res.status_code in (200, 201), res.text
    assert res.json()["documentId"]
    assert res.json().get("fileChecks", {}).get("ok") is True
    # Pipeline honesty fields present
    assert "pipelineOk" in res.json() or "pipeline_ok" in res.json()


def test_intake_rejects_oversized_and_mime_spoof():
    intake = LocalIntakeModule(max_bytes=32)
    big = intake.inspect(
        file_name="big.pdf",
        declared_content_type="application/pdf",
        content=b"%PDF-1.4 " + (b"x" * 200),
    )
    assert big.accepted is False
    assert big.rejection_code == "file_too_large"

    spoof = LocalIntakeModule().inspect(
        file_name="fake.pdf",
        declared_content_type="application/pdf",
        content=b"not-a-pdf-at-all",
    )
    assert spoof.accepted is False
    assert spoof.rejection_code == "content_mismatch"


def test_mime_spoof_rejected_via_api(client):
    app = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    ).json()
    res = client.post(
        f"/api/v1/applications/{app['id']}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("fake.pdf", b"not-a-pdf-at-all", "application/pdf")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    assert res.status_code == 415, res.text
    assert res.json().get("code") in ("content_mismatch", "unsupported_file_type", "http_415")
    assert isinstance(res.json().get("detail"), str)


def test_reupload_increments_version(client):
    app = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    ).json()
    for i in range(2):
        res = client.post(
            f"/api/v1/applications/{app['id']}/documents",
            headers=auth_headers("applicant"),
            files={"file": (f"affidavit_v{i}.pdf", b"%PDF-1.4 content", "application/pdf")},
            data={"requirement_code": "AFFIDAVIT"},
        )
        assert res.status_code in (200, 201), res.text
    detail = client.get(f"/api/v1/applications/{app['id']}", headers=auth_headers("officer"))
    assert detail.status_code == 200
    docs = [d for d in detail.json()["documents"] if d["requirementCode"] == "AFFIDAVIT"]
    assert docs
    assert docs[0]["version"] >= 2


def test_production_demo_auth_fail_closed():
    from app.core.config import ConfigurationError, get_settings

    prev_env = os.environ.get("APP_ENV")
    prev_demo = os.environ.get("DEMO_AUTH_ENABLED")
    try:
        os.environ["APP_ENV"] = "production"
        os.environ["DEMO_AUTH_ENABLED"] = "true"
        os.environ["SECRET_KEY"] = "a-sufficiently-long-production-secret-key"
        get_settings.cache_clear()
        with pytest.raises(ConfigurationError):
            get_settings().validate_runtime()
    finally:
        if prev_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = prev_env
        if prev_demo is None:
            os.environ.pop("DEMO_AUTH_ENABLED", None)
        else:
            os.environ["DEMO_AUTH_ENABLED"] = prev_demo
        os.environ["APP_ENV"] = "test"
        os.environ["DEMO_AUTH_ENABLED"] = "true"
        get_settings.cache_clear()


def test_seeded_demo_apps_present(client):
    res = client.get("/api/v1/applications", headers=auth_headers("officer"))
    assert res.status_code == 200
    numbers = {a["applicationNumber"] for a in res.json()}
    assert "PRM-2025-1001" in numbers
    assert "PRM-2025-1002" in numbers
    assert "PRM-2025-1003" in numbers
    # Mismatch scenario has documents
    detail = client.get(
        "/api/v1/applications/app-1001",
        headers=auth_headers("officer"),
    )
    assert detail.status_code == 200
    assert len(detail.json().get("documents") or []) >= 3


def test_concurrent_officer_blocked_on_clarification(client):
    apps = client.get("/api/v1/applications", headers=auth_headers("officer")).json()
    target = next(a for a in apps if a["applicationNumber"] == "PRM-2025-1002")
    start = client.post(
        f"/api/v1/applications/{target['id']}/scrutiny/start",
        headers=auth_headers("officer"),
    )
    assert start.status_code == 200, start.text

    created = client.post(
        "/api/v1/admin/users",
        headers=auth_headers("regional_officer"),
        json={
            "name": "Other Officer",
            "email": "other.officer@praman.local",
            "role": "officer",
        },
    )
    assert created.status_code == 201, created.text
    other_id = created.json()["id"]
    clarify = client.post(
        f"/api/v1/applications/{target['id']}/scrutiny/clarification",
        headers={"X-Demo-Role": "officer", "X-Demo-User-Id": other_id},
        json={"title": "Need more docs", "description": "Please upload affiliation letter"},
    )
    assert clarify.status_code == 409, clarify.text
