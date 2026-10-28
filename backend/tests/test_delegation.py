from __future__ import annotations

from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
RO = auth_headers("regional_officer")


def _create(client):
    res = client.post(
        "/api/v1/applications",
        headers=APPLICANT,
        json={
            "category_code": "EOA",
            "institution_name": "Demo Institute of Technology",
            "program_name": "Information Technology",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_auto_delegate_on_submit(client):
    app_id = _create(client)
    detail = client.get(f"/api/v1/applications/{app_id}", headers=RO)
    assert detail.status_code == 200
    assert detail.json()["assignedOfficer"], "auto-delegate should assign an officer"


def test_officer_only_sees_assigned_applications(client):
    app_id = _create(client)
    mine = client.get("/api/v1/applications", headers=OFFICER).json()
    # At least one of the officers got it; the named demo-officer may or may not
    # be the selected one. Check via regional view then officer filter.
    all_apps = client.get("/api/v1/applications", headers=RO).json()
    target = next(a for a in all_apps if a["id"] == app_id)
    assert target["assignedOfficer"]
    officer_list = client.get("/api/v1/applications", headers=OFFICER).json()
    ids = {a["id"] for a in officer_list}
    # If Rajesh was assigned, he sees it; if Sneha was, Rajesh must not.
    assigned_name = target["assignedOfficer"]
    if assigned_name == "Rajesh Iyer":
        assert app_id in ids
    else:
        assert app_id not in ids


def test_regional_officer_can_list_load_and_reassign(client):
    app_id = _create(client)
    officers = client.get("/api/v1/admin/officers", headers=RO)
    assert officers.status_code == 200, officers.text
    rows = officers.json()
    assert len(rows) >= 2
    assert all("activeCount" in r for r in rows)

    other = next(r for r in rows if r["name"] != "Rajesh Iyer")
    res = client.post(
        f"/api/v1/admin/applications/{app_id}/delegate",
        headers=RO,
        json={"officerId": other["id"]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["assignedOfficer"] == other["name"]


def test_delegation_settings_roundtrip(client):
    got = client.get("/api/v1/admin/delegation/settings", headers=RO)
    assert got.status_code == 200
    put = client.put(
        "/api/v1/admin/delegation/settings",
        headers=RO,
        json={"max_queue_cap": 15, "active_count_weight": 4},
    )
    assert put.status_code == 200, put.text
    assert put.json()["max_queue_cap"] == 15
    assert put.json()["active_count_weight"] == 4


def test_officer_forbidden_from_delegation_apis(client):
    assert client.get("/api/v1/admin/officers", headers=OFFICER).status_code == 403
    assert client.get("/api/v1/admin/delegation/queue", headers=APPLICANT).status_code == 403
