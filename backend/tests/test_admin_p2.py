"""P2 administrator regressions.

Covers: rule version activation/reactivation without touching history, draft versions that never
act until activated, JSON import validation, natural-language drafts that require review, honest
integration/health status (no secrets), enforced upload policy, detailed searchable audit trail,
and admin-only access to all of it.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.core import runtime_config
from app.core.database import SessionLocal
from app.models.validation import Finding
from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
ADMIN = auth_headers("admin")
A = "/api/v1/admin"


def _uid() -> str:
    return uuid.uuid4().hex[:6].upper()


def _rule(client, code: str):
    rules = client.get(f"{A}/rules", headers=ADMIN).json()
    return next(r for r in rules if r["ruleCode"] == code)


def _make_app(client, file_name: str, body: bytes = b"Institution Name: Alpha College\n"):
    res = client.post(
        "/api/v1/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    app_id = res.json()["id"]
    up = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": (file_name, body, "text/plain")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    assert up.status_code == 200, up.text
    return app_id


def _findings(client, app_id, rule_code="SYN-RULE-003"):
    review = client.get(f"/api/v1/applications/{app_id}/scrutiny-review", headers=OFFICER).json()
    out = []
    for g in review["issueGroups"]:
        for i in g["issues"]:
            out.append(i)
    detail = client.get(f"/api/v1/applications/{app_id}", headers=OFFICER).json()
    return [f for f in detail["findings"] if f.get("ruleId") == rule_code], out


def _revalidate(client, app_id):
    res = client.post(f"/api/v1/applications/{app_id}/validation-runs", headers=OFFICER)
    assert res.status_code == 200, res.text


# ============================ rule versions ==================================================


def test_activation_retires_previous_and_reactivation_really_takes_effect(client):
    code = f"SYN-RULE-V{_uid()}"
    created = client.post(
        f"{A}/rules",
        headers=ADMIN,
        json={"code": code, "name": "Version test", "definition": {"logic": "missing_mandatory", "synthetic": True}},
    ).json()
    rid = created["id"]
    v2 = client.post(
        f"{A}/rules/{rid}/versions",
        headers=ADMIN,
        json={"version": "v2", "definition": {"logic": "missing_mandatory", "synthetic": True},
              "change_reason": "second version", "publish": True},
    ).json()
    states = {v["version"]: v["status"] for v in v2["versions"]}
    assert states == {"v1": "retired", "v2": "published"}

    back = client.post(f"{A}/rules/{rid}/versions/v1/reactivate?reason=rollback after review", headers=ADMIN)
    assert back.status_code == 200, back.text
    body = back.json()
    states = {v["version"]: v for v in body["versions"]}
    assert body["currentVersion"] == "v1"
    assert states["v1"]["status"] == "published" and states["v1"]["effectiveTo"] is None
    assert states["v2"]["status"] == "retired"
    # Exactly one version is live, and it is the one the engine will use.
    from app.services.admin_service import active_rule_runtimes

    db = SessionLocal()
    try:
        runtimes, _ = active_rule_runtimes(db)
    finally:
        db.close()
    assert runtimes[code].version == "v1"
    # Activating what is already active is a conflict, not a silent rewrite.
    again = client.post(f"{A}/rules/{rid}/versions/v1/publish", headers=ADMIN)
    assert again.status_code == 409


def test_new_version_affects_only_future_runs_and_old_findings_keep_their_version(client):
    rule = _rule(client, "SYN-RULE-003")
    original = rule["currentVersion"]
    version = f"v-p2-{_uid().lower()}"
    app_id = _make_app(client, "affidavit_expired.txt")
    old_findings, _ = _findings(client, app_id)
    assert old_findings and all(f["ruleVersion"] == original for f in old_findings)
    try:
        res = client.post(
            f"{A}/rules/{rule['id']}/versions",
            headers=ADMIN,
            json={"version": version,
                  "definition": {"logic": "filename_contains_expired", "synthetic": True,
                                 "params": {"filename_keywords": ["expired", "lapsed"]}},
                  "change_reason": "also treat 'lapsed' as expired", "publish": True},
        )
        assert res.status_code == 201, res.text
        # Past results are untouched: the stored findings still carry the old version.
        db = SessionLocal()
        try:
            rows = db.query(Finding).filter(Finding.rule_code == "SYN-RULE-003", Finding.rule_version == original).all()
            assert any(r.document_id for r in rows)
        finally:
            db.close()
        usage = client.get(f"{A}/rules/{rule['id']}/usage", headers=ADMIN).json()
        assert usage["findingsByVersion"].get(original, 0) >= 1

        # A new run on a different application uses the new version.
        app2 = _make_app(client, "affidavit_lapsed.txt")
        new_findings, _ = _findings(client, app2)
        assert new_findings and all(f["ruleVersion"] == version for f in new_findings)
    finally:
        client.post(f"{A}/rules/{rule['id']}/versions/{original}/reactivate?reason=restore test state", headers=ADMIN)
    assert _rule(client, "SYN-RULE-003")["currentVersion"] == original


def test_draft_version_has_no_effect_until_activated(client):
    rule = _rule(client, "SYN-RULE-003")
    original = rule["currentVersion"]
    version = f"v-draft-{_uid().lower()}"
    res = client.post(
        f"{A}/rules/{rule['id']}/versions",
        headers=ADMIN,
        json={"version": version,
              "definition": {"logic": "filename_contains_expired", "synthetic": True,
                             "params": {"filename_keywords": ["qqdraft"]}},
              "change_reason": "draft for review", "publish": False},
    )
    assert res.status_code == 201
    try:
        assert res.json()["currentVersion"] == original
        app_id = _make_app(client, "file_qqdraft.txt")
        found, _ = _findings(client, app_id)
        assert not found, "a draft version must not be used by the engine"

        pub = client.post(f"{A}/rules/{rule['id']}/versions/{version}/publish?reason=reviewed", headers=ADMIN)
        assert pub.status_code == 200, pub.text
        _revalidate(client, app_id)
        found, _ = _findings(client, app_id)
        assert found and found[0]["ruleVersion"] == version
    finally:
        client.post(f"{A}/rules/{rule['id']}/versions/{original}/reactivate?reason=restore test state", headers=ADMIN)


def test_only_unactivated_drafts_can_be_discarded(client):
    code = f"SYN-RULE-D{_uid()}"
    rid = client.post(f"{A}/rules", headers=ADMIN,
                      json={"code": code, "name": "Discard test", "definition": {"logic": "missing_mandatory"}}).json()["id"]
    client.post(f"{A}/rules/{rid}/versions", headers=ADMIN,
                json={"version": "v2", "definition": {"logic": "missing_mandatory"}, "change_reason": "draft v2"})
    gone = client.post(f"{A}/rules/{rid}/versions/v2/discard?reason=not needed", headers=ADMIN)
    assert gone.status_code == 200
    assert {v["version"]: v["status"] for v in gone.json()["versions"]}["v2"] == "discarded"
    assert client.post(f"{A}/rules/{rid}/versions/v2/publish", headers=ADMIN).status_code == 422
    published = client.post(f"{A}/rules/{rid}/versions/v1/discard?reason=trying to erase history", headers=ADMIN)
    assert published.status_code == 422


def test_rule_params_are_validated_for_builtin_rules(client):
    ok = client.post(f"{A}/rules/validate", headers=ADMIN, json={
        "code": "SYN-RULE-003", "name": "x", "definition": {"logic": "filename_contains_expired",
                                                             "params": {"warn_within_days": -5}}})
    body = ok.json()
    assert body["valid"] is False and any("warn_within_days" in e for e in body["errors"])


# ============================ import & natural language ======================================


def test_import_validate_reports_syntax_errors_with_position(client):
    res = client.post(f"{A}/rules/import/validate", headers=ADMIN, json={"json_text": '{"rules": [ {"code": "A" '}).json()
    assert res["valid"] is False
    assert "line 1" in res["fileErrors"][0] and "column" in res["fileErrors"][0]


def test_import_validates_each_item_and_rejects_the_whole_file_if_any_is_bad(client):
    good = f"SYN-IMP-{_uid()}"
    payload = {"rules": [
        {"code": good, "name": "Good import", "definition": {"logic": "missing_mandatory"}},
        {"code": "SYN-IMP-BAD", "name": "Official without source", "isSynthetic": False,
         "definition": {"logic": "missing_mandatory"}},
        {"code": good, "name": "duplicate in file", "definition": {"logic": "missing_mandatory"}},
        "not an object",
    ]}
    text = json.dumps(payload)
    check = client.post(f"{A}/rules/import/validate", headers=ADMIN, json={"json_text": text}).json()
    assert check["valid"] is False
    by_index = {r["index"]: r for r in check["results"]}
    assert by_index[1]["valid"] is True
    assert any("verified_source_ref" in e for e in by_index[2]["errors"])
    assert any("more than once" in e for e in by_index[3]["errors"])
    assert by_index[4]["valid"] is False
    res = client.post(f"{A}/rules/import", headers=ADMIN, json={"json_text": text})
    assert res.status_code == 422
    assert good not in [r["ruleCode"] for r in client.get(f"{A}/rules", headers=ADMIN).json()]


def test_import_saves_drafts_only_and_never_activates(client):
    code = f"SYN-IMP-{_uid()}"
    text = json.dumps([{"ruleCode": code, "name": "Imported rule", "definition": {"logic": "missing_mandatory", "synthetic": True}}])
    res = client.post(f"{A}/rules/import", headers=ADMIN, json={"json_text": text})
    assert res.status_code == 201, res.text
    assert res.json()["activated"] == 0
    rule = _rule(client, code)
    assert rule["isActive"] is False
    assert [v["status"] for v in rule["versions"]] == ["draft"]
    from app.services.admin_service import active_rule_runtimes

    db = SessionLocal()
    try:
        runtimes, disabled = active_rule_runtimes(db)
    finally:
        db.close()
    assert code not in runtimes and code in disabled
    events = client.get(f"{A}/audit", headers=ADMIN, params={"action": "admin.rule_draft_created", "q": code}).json()
    assert events["total"] == 1
    # Activating is a separate, explicit, audited step.
    pub = client.post(f"{A}/rules/{rule['id']}/versions/v1/publish?reason=reviewed", headers=ADMIN)
    assert pub.status_code == 200 and pub.json()["isActive"] is True


def test_import_into_existing_rule_adds_a_draft_version_and_keeps_current(client):
    rule = _rule(client, "SYN-RULE-003")
    text = json.dumps([{"code": "SYN-RULE-003", "definition": {"logic": "filename_contains_expired",
                                                             "params": {"warn_within_days": 45}}}])
    res = client.post(f"{A}/rules/import", headers=ADMIN, json={"json_text": text})
    assert res.status_code == 201, res.text
    created = res.json()["created"][0]
    after = _rule(client, "SYN-RULE-003")
    assert after["currentVersion"] == rule["currentVersion"]
    draft = next(v for v in after["versions"] if v["version"] == created["version"])
    assert draft["status"] == "draft"
    client.post(f"{A}/rules/{rule['id']}/versions/{created['version']}/discard?reason=test cleanup", headers=ADMIN)


def test_natural_language_draft_maps_to_a_real_engine_parameter_and_requires_review(client):
    before = len(client.get(f"{A}/rules", headers=ADMIN).json())
    res = client.post(f"{A}/rules/draft-from-text", headers=ADMIN,
                      json={"text": "Warn the officer when a certificate's validity ends within 3 months."}).json()
    assert res["requiresReview"] is True and res["executable"] is True
    draft = res["draft"]
    assert draft["targetRuleCode"] == "SYN-RULE-003"
    assert draft["definition"]["params"]["warn_within_days"] == 90
    assert draft["verifiedSourceRef"] == "" and draft["handbookRef"] == ""
    assert res["validation"]["valid"] is True
    # Previewing saved nothing.
    assert len(client.get(f"{A}/rules", headers=ADMIN).json()) == before

    saved = client.post(f"{A}/rules/drafts", headers=ADMIN, json={"rules": [{
        "code": draft["code"], "version": draft["version"], "definition": draft["definition"],
        "change_reason": draft["changeReason"]}]})
    assert saved.status_code == 201, saved.text
    rule = _rule(client, "SYN-RULE-003")
    assert next(v for v in rule["versions"] if v["version"] == draft["version"])["status"] == "draft"
    assert rule["currentVersion"] != draft["version"]
    # An officer cannot activate it.
    assert client.post(f"{A}/rules/{rule['id']}/versions/{draft['version']}/publish", headers=OFFICER).status_code == 403
    client.post(f"{A}/rules/{rule['id']}/versions/{draft['version']}/discard?reason=test cleanup", headers=ADMIN)


def test_natural_language_draft_is_honest_when_it_cannot_be_executed_and_never_invents_citations(client):
    res = client.post(f"{A}/rules/draft-from-text", headers=ADMIN,
                      json={"text": "As per clause 4.2 on page 17 the library must hold 5000 books."}).json()
    assert res["executable"] is False and res["confidence"] == "low"
    assert any("cannot execute" in w.lower() or "could not be mapped" in " ".join(res["interpretation"]).lower() for w in res["warnings"] + res["interpretation"])
    assert any("not verified" in w.lower() for w in res["warnings"])
    d = res["draft"]
    assert d["handbookRef"] == "" and d["verifiedSourceRef"] == ""
    assert "clause 4.2" not in json.dumps({k: v for k, v in d.items() if k not in ("definition", "description", "name")})
    short = client.post(f"{A}/rules/draft-from-text", headers=ADMIN, json={"text": "hi"})
    assert short.status_code in (422,)


# ============================ integrations ===================================================


def test_integrations_report_real_state_and_expose_no_secrets(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_ai_extraction", True)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_api_key", "sk-super-secret-value")
    res = client.get(f"{A}/integrations", headers=ADMIN)
    assert res.status_code == 200
    assert "sk-super-secret-value" not in res.text
    items = {i["id"]: i for i in res.json()["items"]}
    for expected in ("database", "file_storage", "ocr", "llm_extraction", "geocode_nominatim",
                     "pdf_signature", "fire_certificate", "aicte_payment", "aicte_api", "job_runner"):
        assert expected in items
    assert items["database"]["health"] in ("healthy", "degraded")
    llm = items["llm_extraction"]
    assert llm["credentialsConfigured"] is True and llm["health"] == "healthy"
    assert "not live-tested" in llm["message"].lower()
    # No authorized connectors in this build → never reported as healthy/verified.
    assert items["fire_certificate"]["health"] == "not_configured"
    assert items["fire_certificate"]["effectiveEnabled"] is False
    assert items["aicte_api"]["health"] in ("not_configured", "degraded")


def test_admin_kill_switch_blocks_adapter_and_is_audited(client):
    from app.models.enums import VerificationStatus
    from app.verification_engine.adapters.registry import get_adapter
    from app.verification_engine.adapters.types import AdapterContext

    ctx = AdapterContext(document_id="d", document_version_id="v", requirement_code="FIRE_NOC",
                         file_path=None, mime_type="application/pdf", fields={})
    try:
        off = client.put(f"{A}/integrations/fire_certificate", headers=ADMIN,
                         json={"enabled": False, "reason": "Issuer maintenance window"})
        assert off.status_code == 200, off.text
        assert off.json()["health"] == "disabled" and off.json()["adminEnabled"] is False
        result = get_adapter("fire_certificate")(ctx)
        assert result.status == VerificationStatus.SOURCE_UNAVAILABLE
        assert "switched off by an administrator" in result.detail
        assert client.put(f"{A}/integrations/fire_certificate", headers=ADMIN,
                          json={"enabled": False, "reason": "x"}).status_code == 422
        events = client.get(f"{A}/audit", headers=ADMIN, params={"action": "admin.integration_toggled"}).json()
        top = events["items"][0]
        assert top["metadata"]["integration"] == "fire_certificate"
        assert top["metadata"]["after"] == {"enabled": False}
    finally:
        on = client.put(f"{A}/integrations/fire_certificate", headers=ADMIN,
                        json={"enabled": True, "reason": "maintenance finished"})
    assert on.json()["adminEnabled"] is True
    # Re-enabling never makes an unconfigured source live.
    assert on.json()["health"] == "not_configured" and on.json()["effectiveEnabled"] is False
    assert runtime_config.integration_disabled_by_admin("fire_certificate") is False


def test_core_infrastructure_cannot_be_switched_off_and_unknown_ids_404(client):
    assert client.put(f"{A}/integrations/database", headers=ADMIN,
                      json={"enabled": False, "reason": "no thanks"}).status_code == 422
    assert client.get(f"{A}/integrations/nope", headers=ADMIN).status_code == 404


def test_integration_check_records_the_outcome_without_calling_paid_services(client):
    aicte = client.post(f"{A}/integrations/aicte_api/check", headers=ADMIN).json()
    assert aicte["lastCheck"]["ok"] is None and "No safe live probe" in aicte["lastCheck"]["message"]
    db_check = client.post(f"{A}/integrations/database/check", headers=ADMIN).json()
    assert db_check["lastCheck"]["ok"] is True
    issuer = client.post(f"{A}/integrations/fire_certificate/check", headers=ADMIN).json()
    assert issuer["lastCheck"]["ok"] is False and "nothing to probe" in issuer["lastCheck"]["message"]


def test_integration_and_health_endpoints_are_admin_only(client):
    for path in ("/integrations", "/integrations/database", "/system-health", "/audit", "/audit/facets",
                 "/audit/export.csv", "/rules/x/usage"):
        for who in (APPLICANT, OFFICER):
            assert client.get(f"{A}{path}", headers=who).status_code == 403, (path, who)
    for path, body in (("/rules/import", {"json_text": "[]"}), ("/rules/draft-from-text", {"text": "x" * 20}),
                       ("/rules/import/validate", {"json_text": "[]"})):
        for who in (APPLICANT, OFFICER):
            assert client.post(f"{A}{path}", headers=who, json=body).status_code == 403, (path, who)
    assert client.get(f"{A}/system-health").status_code in (401, 403)


# ============================ system health ===================================================


def test_system_health_rolls_up_components_activity_and_warnings(client):
    res = client.get(f"{A}/system-health", headers=ADMIN)
    assert res.status_code == 200, res.text
    body = res.json()
    ids = {c["id"] for c in body["components"]}
    assert {"database", "file_storage", "audit_chain", "rule_engine", "ocr", "pdf_extraction"} <= ids
    assert body["status"] in ("ok", "degraded", "unavailable")
    assert "applicationsTotal" in body["activity"] and body["activity"]["windowHours"] == 24
    assert any("demo header authentication" in w.lower() for w in body["warnings"])
    assert sum(body["integrationSummary"].values()) >= 10
    audit = next(c for c in body["components"] if c["id"] == "audit_chain")
    assert audit["health"] == "healthy"


def test_system_health_turns_unavailable_when_storage_cannot_be_written(client, monkeypatch, tmp_path):
    from app.core.config import settings

    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    monkeypatch.setattr(settings, "upload_dir", str(blocker / "uploads"))
    body = client.get(f"{A}/system-health", headers=ADMIN).json()
    storage = next(c for c in body["components"] if c["id"] == "file_storage")
    assert storage["health"] == "unavailable"
    assert body["status"] == "unavailable"


# ============================ settings are enforced, not decorative ===========================


def test_upload_policy_setting_is_enforced_and_only_narrows_deployment_limits(client):
    default = {"maxUploadMb": 25, "allowedExtensions": ["pdf", "png", "jpg", "jpeg", "docx", "txt"],
               "autoExtractOnUpload": True}
    try:
        res = client.put(f"{A}/settings/uploads", headers=ADMIN,
                         json={"value": {"maxUploadMb": 1, "allowedExtensions": ["pdf"], "autoExtractOnUpload": True},
                               "change_reason": "tighten policy"})
        assert res.status_code == 200, res.text
        policy = client.get("/api/v1/applications/upload-policy", headers=APPLICANT).json()
        assert policy["maxUploadMb"] == 1 and policy["allowedExtensions"] == ["pdf"]
        app_id = _make_app_no_upload(client)
        rejected = client.post(f"/api/v1/applications/{app_id}/documents", headers=APPLICANT,
                               files={"file": ("a.txt", b"hello", "text/plain")}, data={"requirement_code": "AFFIDAVIT"})
        assert rejected.status_code == 415, rejected.text
    finally:
        client.put(f"{A}/settings/uploads", headers=ADMIN, json={"value": default, "change_reason": "restore defaults"})
    assert client.get("/api/v1/applications/upload-policy", headers=APPLICANT).json()["maxUploadMb"] == 25


def _make_app_no_upload(client):
    return client.post("/api/v1/applications", headers=APPLICANT, json={
        "category_code": "NEW-ENG", "institution_name": "Policy Institute", "program_name": "B.Tech",
        "academic_year": "2025-26"}).json()["id"]


@pytest.mark.parametrize(
    "key,value,fragment",
    [
        ("uploads", {"maxUploadMb": 999}, "deployment limit"),
        ("uploads", {"allowedExtensions": ["exe"]}, "not allowed by the deployment"),
        ("uploads", {"maxUploadMb": "ten"}, "whole number"),
        ("uploads", {"mystery": 1}, "Unknown field"),
        ("verification", {"enableLiveVerification": True}, "server configuration"),
        ("verification", {"maxConcurrentVerificationRequests": 0}, "between 1 and 50"),
    ],
)
def test_invalid_or_over_reaching_settings_are_rejected(client, key, value, fragment):
    res = client.put(f"{A}/settings/{key}", headers=ADMIN, json={"value": value, "change_reason": "attempt"})
    assert res.status_code == 422, res.text
    assert fragment in res.json()["detail"]


def test_integration_switches_cannot_be_edited_as_a_raw_setting(client):
    res = client.put(f"{A}/settings/integrations", headers=ADMIN,
                     json={"value": {"overrides": {}}, "change_reason": "sneaky"})
    assert res.status_code == 422
    keys = [s["key"] for s in client.get(f"{A}/settings", headers=ADMIN).json()]
    assert "integrations" not in keys


def test_settings_expose_which_fields_are_actually_enforced(client):
    rows = {s["key"]: s for s in client.get(f"{A}/settings", headers=ADMIN).json()}
    assert "enforced" in rows["uploads"]["enforcement"]["maxUploadMb"]
    assert "deployment" in rows["verification"]["enforcement"]["enableLiveVerification"]
    stats = client.get(f"{A}/stats", headers=ADMIN).json()
    from app.core.config import settings

    assert stats["liveVerificationEnabled"] is bool(settings.enable_live_verification)


# ============================ audit trail ======================================================


def test_audit_search_filters_facets_detail_and_application_number(client):
    app_id = _make_app(client, "audit_probe.txt")
    number = client.get(f"/api/v1/applications/{app_id}", headers=OFFICER).json()["applicationNumber"]
    by_number = client.get(f"{A}/audit", headers=ADMIN, params={"application_number": number}).json()
    assert by_number["total"] >= 1
    assert all(i["applicationId"] == app_id and i["applicationNumber"] == number for i in by_number["items"])
    free = client.get(f"{A}/audit", headers=ADMIN, params={"q": number}).json()
    assert free["total"] >= by_number["total"]

    code = f"SYN-AUD-{_uid()}"
    client.post(f"{A}/rules", headers=ADMIN, json={"code": code, "name": "Audit probe rule",
                                                    "definition": {"logic": "missing_mandatory"}})
    by_cat = client.get(f"{A}/audit", headers=ADMIN, params={"category": "admin", "actor_role": "admin", "q": code}).json()
    assert by_cat["total"] >= 1 and all(i["category"] == "admin" and i["actorRole"] == "admin" for i in by_cat["items"])
    nothing = client.get(f"{A}/audit", headers=ADMIN, params={"actor_role": "applicant", "category": "admin"}).json()
    assert nothing["total"] == 0

    facets = client.get(f"{A}/audit/facets", headers=ADMIN).json()
    assert "admin" in [c["value"] for c in facets["categories"]]
    assert facets["total"] >= by_cat["total"]

    event = by_cat["items"][0]
    detail = client.get(f"{A}/audit/{event['id']}", headers=ADMIN).json()
    assert detail["id"] == event["id"] and "related" in detail and detail["label"]
    assert client.get(f"{A}/audit/does-not-exist", headers=ADMIN).status_code == 404


def test_setting_and_rule_changes_record_before_and_after(client):
    version = f"v-aud-{_uid().lower()}"
    rule = _rule(client, "SYN-RULE-003")
    original = rule["currentVersion"]
    try:
        client.post(f"{A}/rules/{rule['id']}/versions", headers=ADMIN, json={
            "version": version, "definition": {"logic": "filename_contains_expired", "params": {"warn_within_days": 30}},
            "change_reason": "audit detail check", "publish": True})
        ev = client.get(f"{A}/audit", headers=ADMIN, params={"action": "admin.rule_version_created", "q": version}).json()["items"][0]
        assert ev["metadata"]["previousCurrentVersion"] == original
        assert ev["metadata"]["definition"]["params"]["warn_within_days"] == 30
        assert ev["metadata"]["reason"] == "audit detail check"
    finally:
        client.post(f"{A}/rules/{rule['id']}/versions/{original}/reactivate?reason=restore test state", headers=ADMIN)
    client.put(f"{A}/settings/verification", headers=ADMIN, json={
        "value": {"preferSimulatedAdapters": False}, "change_reason": "audit before/after"})
    sev = client.get(f"{A}/audit", headers=ADMIN, params={"action": "admin.setting_updated"}).json()["items"][0]
    assert sev["metadata"]["key"] == "verification"
    assert "preferSimulatedAdapters" in sev["metadata"]["changedFields"]
    assert sev["metadata"]["after"]["preferSimulatedAdapters"] is False
    client.put(f"{A}/settings/verification", headers=ADMIN, json={
        "value": {"enableLiveVerification": False, "preferSimulatedAdapters": True,
                  "requireManualReviewOnUnavailable": True, "maxConcurrentVerificationRequests": 5},
        "change_reason": "restore defaults"})


def test_audit_csv_export_is_filtered_audited_and_formula_safe(client):
    from app.api.routes.admin import _csv_cell

    assert _csv_cell("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert _csv_cell("+1") == "'+1" and _csv_cell("@cmd") == "'@cmd" and _csv_cell("normal") == "normal"
    res = client.get(f"{A}/audit/export.csv", headers=ADMIN, params={"category": "admin"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.lstrip("\ufeff").splitlines()
    assert lines[0].startswith("timestamp,action,category,actor")
    assert len(lines) > 1
    logged = client.get(f"{A}/audit", headers=ADMIN, params={"action": "admin.audit_exported"}).json()
    assert logged["total"] >= 1


def test_disabling_a_rule_actually_stops_it_running_and_enabling_restores_it(client):
    # Regression: the rule lookup crashed on naive/aware datetimes and was silently swallowed, so
    # administrator switches and versions never reached the engine.
    rule = _rule(client, "SYN-RULE-003")
    app_id = _make_app(client, "scan_expired.txt")
    assert _findings(client, app_id)[0], "baseline: the rule fires"
    try:
        off = client.patch(f"{A}/rules/{rule['id']}", headers=ADMIN, json={"is_active": False, "change_reason": "pause rule"})
        assert off.status_code == 200
        _revalidate(client, app_id)
        assert not _findings(client, app_id)[0]
    finally:
        client.patch(f"{A}/rules/{rule['id']}", headers=ADMIN, json={"is_active": True, "change_reason": "resume rule"})
    _revalidate(client, app_id)
    assert _findings(client, app_id)[0]
