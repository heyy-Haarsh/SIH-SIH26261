"""Phase 7: three-layer document verification engine."""

from pathlib import Path

from tests.conftest import auth_headers


def _create_app(client):
    res = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech CSE",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()


def _upload(client, app_id: str, req_code: str, name: str, content: bytes = b"%PDF-1.4 demo"):
    files = {"file": (name, content, "application/pdf")}
    data = {"requirement_code": req_code}
    res = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files=files,
        data=data,
    )
    assert res.status_code in (200, 201), res.text
    return res.json()


def test_configs_list_six_document_types(client):
    res = client.get("/api/v1/document-verification/configs", headers=auth_headers("officer"))
    assert res.status_code == 200
    codes = {c["requirementCode"] for c in res.json()}
    assert "AICTE_PAYMENT_RECEIPT" in codes
    assert "OCCUPANCY_CERTIFICATE" in codes
    assert "STRUCTURAL_STABILITY" in codes
    assert "FIRE_NOC" in codes
    assert "SATELLITE_MAP" in codes
    assert "AUDITED_ACCOUNTS" in codes
    assert all(c.get("isSyntheticRules") is True for c in res.json())


def test_layer1_fail_does_not_imply_authenticity(client):
    app = _create_app(client)
    _upload(client, app["id"], "FIRE_NOC", "fire_noc_blank.pdf")
    runs = client.post(
        f"/api/v1/applications/{app['id']}/document-verification",
        headers=auth_headers("officer"),
    )
    assert runs.status_code == 200, runs.text
    body = runs.json()
    assert len(body) >= 1
    run = body[0]
    assert run["ruleValidationStatus"] in ("fail", "manual_review", "warning", "unreadable", "pass")
    # External must not be verified_by_source for unauthorized stubs
    assert run["externalVerificationStatus"] != "verified_by_source"
    assert run["externalVerificationStatus"] in (
        "source_unavailable",
        "manual_verification_required",
        "partial",
        "not_applicable",
        "simulated_result",
        "pending",
        "mismatch_detected",
    )
    report = run.get("scrutinyReport") or {}
    assert "never automatically establish authenticity" in (report.get("disclaimer") or "").lower() or any(
        "authenticity" in (l or "").lower() for l in (run.get("limitations") or [])
    )


def test_payment_receipt_pipeline_and_rbac(client):
    app = _create_app(client)
    _upload(client, app["id"], "AICTE_PAYMENT_RECEIPT", "aicte_payment_receipt.pdf")
    # Internal verification is staff-only; an applicant must not be able to trigger or read it.
    denied = client.post(
        f"/api/v1/applications/{app['id']}/document-verification",
        headers=auth_headers("applicant"),
    )
    assert denied.status_code == 403
    ok = client.post(
        f"/api/v1/applications/{app['id']}/document-verification",
        headers=auth_headers("officer"),
    )
    assert ok.status_code == 200, ok.text
    run = ok.json()[0]
    assert run["configCode"] == "AICTE_PAYMENT_RECEIPT"
    layers = {c["layer"] for c in run["checks"]}
    assert "layer1_rules" in layers
    assert "layer2_external" in layers
    # Officer resolve requires reason
    open_check = next(c for c in run["checks"] if c["status"] == "open")
    bad = client.post(
        f"/api/v1/document-verification-checks/{open_check['id']}/resolve",
        headers=auth_headers("applicant"),
        json={"status": "resolved", "reason": "looks fine to me"},
    )
    assert bad.status_code == 403
    good = client.post(
        f"/api/v1/document-verification-checks/{open_check['id']}/resolve",
        headers=auth_headers("officer"),
        json={"status": "waived", "reason": "Accepted pending municipal confirmation"},
    )
    assert good.status_code == 200, good.text
    assert good.json()["status"] == "waived"


def test_satellite_geocode_disabled_is_source_unavailable(client):
    app = _create_app(client)
    _upload(client, app["id"], "SATELLITE_MAP", "campus_satellite_map.pdf")
    res = client.post(
        f"/api/v1/applications/{app['id']}/document-verification",
        headers=auth_headers("officer"),
    )
    assert res.status_code == 200
    run = res.json()[0]
    geo = [c for c in run["checks"] if c["adapter"] == "geocode_nominatim"]
    assert geo
    assert geo[0]["outcome"] == "source_unavailable"
    assert geo[0]["source"] in ("authorized_live", "local_validation")


def test_validation_run_triggers_doc_verification(client):
    app = _create_app(client)
    _upload(client, app["id"], "STRUCTURAL_STABILITY", "structural_stability.pdf")
    val = client.post(
        f"/api/v1/applications/{app['id']}/validation-runs",
        headers=auth_headers("officer"),
    )
    assert val.status_code in (200, 201), val.text
    summary = val.json().get("summary") or {}
    # May be nested differently depending on serializer — also check detail
    detail = client.get(f"/api/v1/applications/{app['id']}", headers=auth_headers("officer"))
    assert detail.status_code == 200
    docs = detail.json().get("documents") or []
    struct = next(d for d in docs if d["requirementCode"] == "STRUCTURAL_STABILITY")
    assert struct.get("ruleValidationStatus")
    assert struct.get("externalVerificationStatus")
    assert struct.get("reviewStatus")
    runs = detail.json().get("documentVerificationRuns") or []
    assert any(r.get("configCode") == "STRUCTURAL_STABILITY" for r in runs)


def test_layer1_unit_missing_fields():
    from app.verification_engine.layer1 import evaluate_layer1
    from app.verification_engine.loader import get_config_for_requirement

    cfg = get_config_for_requirement("FIRE_NOC")
    assert cfg
    result = evaluate_layer1(cfg, {})
    assert result.status == "fail"
    assert any(c.outcome == "fail" for c in result.checks)
