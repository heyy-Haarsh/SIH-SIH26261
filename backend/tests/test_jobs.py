"""Admin processing-job view: derived from real run records, admin-only."""

from __future__ import annotations

from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
ADMIN = auth_headers("regional_officer")
API = "/api/v1/admin"


def _submit_app(client):
    res = client.post(
        "/api/v1/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Jobs Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_jobs_are_admin_only(client):
    assert client.get(f"{API}/jobs", headers=APPLICANT).status_code == 403
    assert client.get(f"{API}/jobs", headers=OFFICER).status_code == 403
    assert client.get(f"{API}/jobs").status_code in (401, 403)


def test_jobs_list_validation_runs_with_outcome_counts(client):
    app_id = _submit_app(client)
    run = client.post(f"/api/v1/applications/{app_id}/validation-runs", headers=OFFICER)
    assert run.status_code in (200, 201), run.text

    res = client.get(f"{API}/jobs", headers=ADMIN)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body, body
    mine = [j for j in body["items"] if j["applicationId"] == app_id and j["kind"] == "validation"]
    assert mine, body
    job = mine[0]
    assert job["applicationNumber"]
    assert job["outcome"] in {"ok", "active", "failed", "needs_attention"}
    assert sum(body["counts"].values()) == len(body["items"])


def test_jobs_filters_and_validation(client):
    _submit_app(client)
    only = client.get(f"{API}/jobs", headers=ADMIN, params={"kind": "extraction"}).json()
    assert all(j["kind"] == "extraction" for j in only["items"])
    failed = client.get(f"{API}/jobs", headers=ADMIN, params={"outcome": "failed"}).json()
    assert all(j["outcome"] == "failed" for j in failed["items"])
    assert client.get(f"{API}/jobs", headers=ADMIN, params={"kind": "bogus"}).status_code == 422
