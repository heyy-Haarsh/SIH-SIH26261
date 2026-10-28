"""Phase 6: admin CRUD, rule versioning/publish, audit search, RBAC."""

from tests.conftest import auth_headers


def test_applicant_forbidden_from_admin_mutation(client):
    res = client.post(
        "/api/v1/admin/users",
        headers=auth_headers("applicant"),
        json={
            "name": "X",
            "email": "x@example.com",
            "role": "officer",
        },
    )
    assert res.status_code == 403


def test_officer_cannot_search_audit(client):
    res = client.get("/api/v1/admin/audit", headers=auth_headers("officer"))
    assert res.status_code == 403


def test_admin_users_crud(client):
    create = client.post(
        "/api/v1/admin/users",
        headers=auth_headers("regional_officer"),
        json={
            "name": "New Officer",
            "email": "new.officer@praman.local",
            "role": "officer",
            "is_active": True,
        },
    )
    assert create.status_code == 201, create.text
    uid = create.json()["id"]

    patch = client.patch(
        f"/api/v1/admin/users/{uid}",
        headers=auth_headers("regional_officer"),
        json={"is_active": False, "change_reason": "Offboarding for demo"},
    )
    assert patch.status_code == 200
    assert patch.json()["isActive"] is False

    listing = client.get("/api/v1/admin/users", headers=auth_headers("regional_officer"))
    assert listing.status_code == 200
    assert any(u["id"] == uid for u in listing.json())


def test_category_crud(client):
    res = client.post(
        "/api/v1/admin/categories",
        headers=auth_headers("regional_officer"),
        json={
            "code": "DEMO-CAT",
            "name": "Demo Category",
            "description": "Test",
            "required_documents": [
                {"code": "AFFIDAVIT", "name": "Affidavit", "mandatory": True, "allowed_types": ["pdf"]}
            ],
        },
    )
    assert res.status_code == 201, res.text
    cid = res.json()["id"]

    dup = client.post(
        "/api/v1/admin/categories",
        headers=auth_headers("regional_officer"),
        json={"code": "DEMO-CAT", "name": "Dup"},
    )
    assert dup.status_code in (409, 422)

    upd = client.patch(
        f"/api/v1/admin/categories/{cid}",
        headers=auth_headers("regional_officer"),
        json={"is_active": False, "change_reason": "Disable unused category"},
    )
    assert upd.status_code == 200
    assert upd.json()["isActive"] is False


def test_rule_validate_rejects_invented_official(client):
    res = client.post(
        "/api/v1/admin/rules/validate",
        headers=auth_headers("regional_officer"),
        json={
            "code": "AICTE-FAKE-1",
            "name": "Fake official",
            "is_synthetic": False,
            "handbook_ref": "Demo handbook placeholder",
            "verified_source_ref": "",
            "definition": {"logic": "missing_mandatory"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is False
    assert any("verified_source" in e.lower() or "official" in e.lower() for e in body["errors"])


def test_rule_version_history_never_overwrites(client):
    create = client.post(
        "/api/v1/admin/rules",
        headers=auth_headers("regional_officer"),
        json={
            "code": "SYN-RULE-ADMIN-1",
            "name": "Admin test rule",
            "description": "Synthetic only",
            "is_synthetic": True,
            "definition": {"logic": "missing_mandatory", "synthetic": True},
            "version": "v1",
            "change_reason": "Initial synthetic rule",
        },
    )
    assert create.status_code == 201, create.text
    rule = create.json()
    rid = rule["id"]
    assert len(rule["versions"]) == 1
    v1_def = rule["versions"][0]["definition"]

    v2 = client.post(
        f"/api/v1/admin/rules/{rid}/versions",
        headers=auth_headers("regional_officer"),
        json={
            "version": "v2",
            "definition": {"logic": "missing_mandatory", "params": {"strict": True}, "synthetic": True},
            "change_reason": "Tighten checklist parameters",
            "publish": True,
        },
    )
    assert v2.status_code == 201, v2.text
    body = v2.json()
    assert body["currentVersion"] == "v2"
    versions = {v["version"]: v for v in body["versions"]}
    assert "v1" in versions and "v2" in versions
    # Historical definition intact
    assert versions["v1"]["definition"] == v1_def
    # Superseded versions are retired (kept, with a closed effective window) — never deleted/edited
    assert versions["v1"]["status"] == "retired"
    assert versions["v1"]["effectiveTo"] is not None
    assert versions["v2"]["status"] == "published"
    assert versions["v2"]["effectiveTo"] is None

    # Duplicate version id rejected
    dup = client.post(
        f"/api/v1/admin/rules/{rid}/versions",
        headers=auth_headers("regional_officer"),
        json={
            "version": "v2",
            "definition": {"logic": "missing_mandatory"},
            "change_reason": "Should fail duplicate",
            "publish": False,
        },
    )
    assert dup.status_code in (409, 422)

    # Reactivate v1
    react = client.post(
        f"/api/v1/admin/rules/{rid}/versions/v1/reactivate?reason=Rollback%20to%20prior%20params",
        headers=auth_headers("regional_officer"),
    )
    assert react.status_code == 200, react.text
    assert react.json()["currentVersion"] == "v1"


def test_disable_rule(client):
    rules = client.get("/api/v1/admin/rules", headers=auth_headers("regional_officer"))
    assert rules.status_code == 200
    seeded = next(r for r in rules.json() if r["ruleCode"].startswith("SYN-RULE-"))
    res = client.patch(
        f"/api/v1/admin/rules/{seeded['id']}",
        headers=auth_headers("regional_officer"),
        json={"is_active": False, "change_reason": "Temporarily disable for demo"},
    )
    assert res.status_code == 200
    assert res.json()["isActive"] is False
    # restore
    client.patch(
        f"/api/v1/admin/rules/{seeded['id']}",
        headers=auth_headers("regional_officer"),
        json={"is_active": True, "change_reason": "Re-enable after demo"},
    )


def test_settings_reject_secrets_and_update(client):
    bad = client.put(
        "/api/v1/admin/settings/verification",
        headers=auth_headers("regional_officer"),
        json={"value": {"api_key": "secret"}, "change_reason": "try secret"},
    )
    assert bad.status_code == 422

    ok = client.put(
        "/api/v1/admin/settings/verification",
        headers=auth_headers("regional_officer"),
        json={
            "value": {
                "enableLiveVerification": False,
                "preferSimulatedAdapters": True,
                "requireManualReviewOnUnavailable": True,
                "maxConcurrentVerificationRequests": 3,
            },
            "change_reason": "Confirm safe defaults",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["value"]["maxConcurrentVerificationRequests"] == 3


def test_audit_search_filter_and_pagination(client):
    # Generate an auditable admin action
    client.post(
        "/api/v1/admin/users",
        headers=auth_headers("regional_officer"),
        json={
            "name": "Audit Probe",
            "email": "audit.probe@praman.local",
            "role": "officer",
        },
    )
    res = client.get(
        "/api/v1/admin/audit?action=admin.user&limit=10&offset=0",
        headers=auth_headers("regional_officer"),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 1
    assert all("api_key" not in str(i.get("metadata", {})).lower() for i in body["items"])
    assert any("admin.user" in i["action"] for i in body["items"])


def test_admin_stats(client):
    res = client.get("/api/v1/admin/stats", headers=auth_headers("regional_officer"))
    assert res.status_code == 200
    body = res.json()
    assert body["userCount"] >= 3
    assert body["activeRuleCount"] >= 1
