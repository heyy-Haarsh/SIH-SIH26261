"""Phase 10 smoke: create app, upload, run verification, fetch report."""

from tests.conftest import auth_headers


def test_full_application_pipeline_smoke(client):
    app = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech CSE",
            "academic_year": "2025-26",
        },
    )
    assert app.status_code in (200, 201), app.text
    app_id = app.json()["id"]

    up = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("fire_noc.pdf", b"%PDF-1.4 demo", "application/pdf")},
        data={"requirement_code": "FIRE_NOC"},
    )
    assert up.status_code in (200, 201), up.text

    runs = client.post(
        f"/api/v1/applications/{app_id}/document-verification",
        headers=auth_headers("officer"),
    )
    assert runs.status_code == 200, runs.text
    body = runs.json()
    assert len(body) >= 1
    run = body[0]
    assert run["ruleValidationStatus"] not in ("pending",)
    assert run["externalVerificationStatus"] not in ("pending",)
    assert "engineResult" in run

    report = client.get(
        f"/api/v1/applications/{app_id}/report.json",
        headers=auth_headers("officer"),
    )
    assert report.status_code == 200
    disc = report.json().get("report_disclaimer") or ""
    assert "competent authority" in disc.lower() or "decision-support" in disc.lower()

    chain = client.get(
        "/api/v1/admin/audit-chain/verify",
        headers=auth_headers("regional_officer"),
    )
    assert chain.status_code == 200
    assert "ok" in chain.json()
