from tests.conftest import auth_headers


def test_missing_role_header_rejected(client):
    res = client.get("/api/v1/applications")
    assert res.status_code == 401


def test_invalid_role_rejected(client):
    res = client.get(
        "/api/v1/applications",
        headers={"X-Demo-Role": "superadmin", "X-Demo-User-Id": "demo-officer"},
    )
    assert res.status_code in (401, 403)


def test_applicant_cannot_list_admin_users(client):
    res = client.get("/api/v1/admin/users", headers=auth_headers("applicant"))
    assert res.status_code == 403


def test_admin_can_list_users(client):
    res = client.get("/api/v1/admin/users", headers=auth_headers("admin"))
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert len(res.json()) >= 3


def test_officer_can_list_applications(client):
    res = client.get("/api/v1/applications", headers=auth_headers("officer"))
    assert res.status_code == 200
    assert any(a["applicationNumber"] == "PRM-2025-1001" for a in res.json())
