"""Category-driven configuration, end to end through the real API.

Covers: administrator configures a category (information fields, document requirements, rules),
publishes it; an applicant gets that configuration; only the intended requirement's published
rules run; results record exact versions; configuration is version-pinned; authorisation holds.
"""

from __future__ import annotations

import uuid

import pytest

from app.rules import definition as rd
from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
ADMIN = auth_headers("regional_officer")
API = "/api/v1"
CFG = f"{API}/admin/config"
CONFIRM = {"confirm_declarations": True}


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def _rule_def(check: dict, on_fail: str = "failed") -> dict:
    return {"schema_version": 1, "check": check, "on_fail": on_fail}


def _make_category(client, *, rule: dict | None = None, source: str = "", requirement_code: str = "CERT") -> dict:
    cat = client.post(f"{CFG}/categories", headers=ADMIN, json={"code": _code("T"), "name": "Test purpose", "description": "Purpose"})
    assert cat.status_code == 201, cat.text
    cid = cat.json()["id"]
    res = client.put(
        f"{CFG}/categories/{cid}/info-fields",
        headers=ADMIN,
        json={"fields": [{"key": "trust_name", "label": "Trust name", "type": "text", "required": True}]},
    )
    assert res.status_code == 200, res.text
    req = client.post(
        f"{CFG}/categories/{cid}/requirements",
        headers=ADMIN,
        json={"code": requirement_code, "name": "Certificate", "allowed_types": ["txt", "pdf"], "mandatory": True},
    )
    assert req.status_code == 201, req.text
    rid = req.json()["id"]
    out = {"category_id": cid, "requirement_id": rid, "code": cat.json()["code"], "rule_id": None}
    if rule is not None:
        r = client.post(
            f"{CFG}/requirements/{rid}/rules",
            headers=ADMIN,
            json={"title": "Certificate check", "description": "d", "definition": rule, "source_reference": source},
        )
        assert r.status_code == 201, r.text
        out["rule_id"] = r.json()["id"]
        a = client.post(f"{CFG}/rules/{out['rule_id']}/versions/1/activate", headers=ADMIN, json={})
        assert a.status_code == 200, a.text
    return out


def _publish(client, cat: dict, active: bool = True):
    res = client.post(f"{CFG}/categories/{cat['category_id']}/publish", headers=ADMIN, json={"note": "test"})
    assert res.status_code == 200, res.text
    if active:
        res = client.patch(f"{CFG}/categories/{cat['category_id']}", headers=ADMIN, json={"is_active": True})
        assert res.status_code == 200, res.text
    return res.json()


def _draft(client, code: str, **info):
    res = client.post(
        f"{API}/applications",
        headers=APPLICANT,
        json={
            "category_code": code,
            "institution_name": "Config Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
            "save_as_draft": True,
            "info_values": info,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _upload(client, app_id: str, code: str, body: str):
    res = client.post(
        f"{API}/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": ("doc.txt", body.encode(), "text/plain")},
        data={"requirement_code": code},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _checks(client, app_id: str, code: str = "CERT") -> list[dict]:
    view = client.get(f"{API}/applicant/applications/{app_id}", headers=APPLICANT).json()
    return next(r for r in view["requirements"] if r["code"] == code)["checks"]


# ---- definition schema (pure) -----------------------------------------------------------------

def test_definition_rejects_unknown_operator_type_and_property():
    bad_op = rd.validate_definition(_rule_def({"type": "field_compare", "field": "payment_amount", "operator": "approx", "value": 5}), source_reference="x")
    assert not bad_op.valid and any("operator" in e for e in bad_op.errors)
    bad_type = rd.validate_definition(_rule_def({"type": "run_python", "code": "1+1"}))
    assert not bad_type.valid and any("Unsupported check type" in e for e in bad_type.errors)
    extra = rd.validate_definition({"schema_version": 1, "check": {"type": "field_present", "field": "address"}, "eval": "x"})
    assert not extra.valid and any("Unknown property" in e for e in extra.errors)
    incompatible = rd.validate_definition(
        _rule_def({"type": "field_compare", "field": "payment_amount", "operator": "gt", "value": "lots", "value_type": "number"}), source_reference="x"
    )
    assert not incompatible.valid


def test_threshold_rules_need_a_source_reference():
    check = {"type": "date_age_max_days", "field": "issue_date", "max_days": 90}
    assert not rd.validate_definition(_rule_def(check)).valid
    assert rd.validate_definition(_rule_def(check), source_reference="Circular 12/2025").valid


def test_unable_to_evaluate_is_not_a_failure():
    definition = _rule_def({"type": "date_not_expired", "field": "valid_until"})
    unreadable = rd.evaluate(definition, rd.RuleInput(fields={}, extraction_state="failed"))
    assert unreadable.state == rd.UNABLE
    pending = rd.evaluate(definition, rd.RuleInput(fields={}, extraction_state="processing"))
    assert pending.state == rd.PENDING
    expired = rd.evaluate(definition, rd.RuleInput(fields={"valid_until": "2001-01-01"}))
    assert expired.state == rd.FAILED


def test_plain_language_suggestion_is_only_a_proposal():
    out = rd.suggest_from_text("The certificate must not be expired and must contain a registration number.")
    assert out["definition"]["check"]["type"] == "date_not_expired"
    assert out["unsupported"], "extra clauses must be reported, not silently dropped"
    assert out["assumptions"]


# ---- administrator workflow -------------------------------------------------------------------

def test_admin_sees_fields_and_requirements_and_invalid_json_is_explained(client):
    cat = _make_category(client)
    detail = client.get(f"{CFG}/categories/{cat['category_id']}", headers=ADMIN).json()
    assert [f["key"] for f in detail["infoFields"]] == ["trust_name"]
    assert [r["code"] for r in detail["requirements"]] == ["CERT"]

    res = client.post(
        f"{CFG}/rule-definitions/validate", headers=ADMIN, json={"definition": "{ not json", "requirement_id": cat["requirement_id"]}
    )
    assert res.status_code == 200 and res.json()["valid"] is False
    assert "could not be parsed" in res.json()["errors"][0]

    unknown = client.post(
        f"{CFG}/requirements/{cat['requirement_id']}/rules",
        headers=ADMIN,
        json={"title": "Bad operator", "definition": _rule_def({"type": "field_compare", "field": "payment_amount", "operator": "approx", "value": 1})},
    )
    assert unknown.status_code == 201  # saved as a draft with its validation errors...
    rule = unknown.json()
    activate = client.post(f"{CFG}/rules/{rule['id']}/versions/1/activate", headers=ADMIN, json={})
    assert activate.status_code == 422 and activate.json()["code"] == "rule_invalid"  # ...but never activated


def test_plain_language_rule_needs_structure_and_explicit_confirmation(client):
    cat = _make_category(client)
    res = client.post(
        f"{CFG}/requirements/{cat['requirement_id']}/rules",
        headers=ADMIN,
        json={"title": "Plain rule", "authoring_mode": "plain", "natural_language": "The certificate should look official."},
    )
    rule = res.json()
    assert rule["status"] == "draft"
    blocked = client.post(f"{CFG}/rules/{rule['id']}/versions/1/activate", headers=ADMIN, json={"confirm_interpretation": True})
    assert blocked.status_code == 422  # no executable definition exists, so text alone cannot become a rule

    saved = client.put(
        f"{CFG}/rules/{rule['id']}/draft",
        headers=ADMIN,
        json={
            "title": "Plain rule",
            "authoring_mode": "plain",
            "natural_language": "The certificate must contain a certificate number.",
            "definition": _rule_def({"type": "field_present", "field": "certificate_number"}),
        },
    )
    assert saved.status_code == 200
    unconfirmed = client.post(f"{CFG}/rules/{rule['id']}/versions/1/activate", headers=ADMIN, json={})
    assert unconfirmed.json()["code"] == "interpretation_not_confirmed"
    ok = client.post(f"{CFG}/rules/{rule['id']}/versions/1/activate", headers=ADMIN, json={"confirm_interpretation": True})
    assert ok.status_code == 200 and ok.json()["status"] == "active"


def test_editing_an_active_rule_creates_a_new_version(client):
    cat = _make_category(client, rule=_rule_def({"type": "field_present", "field": "certificate_number"}))
    edit = client.post(f"{CFG}/rules/{cat['rule_id']}/edit", headers=ADMIN)
    assert edit.status_code == 200
    body = edit.json()
    versions = {v["version"]: v for v in body["versions"]}
    assert versions[1]["status"] == "published" and versions[2]["status"] == "draft"
    assert versions[1]["definition"]["check"]["field"] == "certificate_number"  # history untouched


def test_rule_overview_is_scoped_and_links_to_owner(client):
    a = _make_category(client, rule=_rule_def({"type": "field_present", "field": "certificate_number"}))
    b = _make_category(client, rule=_rule_def({"type": "field_present", "field": "address"}))
    only_a = client.get(f"{CFG}/rules/overview", params={"category_id": a["category_id"]}, headers=ADMIN).json()
    assert {r["id"] for r in only_a} == {a["rule_id"]}
    assert only_a[0]["requirementId"] == a["requirement_id"] and only_a[0]["category"]["id"] == a["category_id"]
    per_req = client.get(f"{CFG}/requirements/{b['requirement_id']}/rules", headers=ADMIN).json()
    assert [r["id"] for r in per_req["rules"]] == [b["rule_id"]]


def test_publish_requires_valid_configuration_and_records_changes(client):
    cat = _make_category(client)
    client.patch(
        f"{CFG}/requirements/{cat['requirement_id']}", headers=ADMIN, json={"allowed_types": ["exe"]}
    )  # rejected by validation
    res = client.post(f"{CFG}/categories/{cat['category_id']}/publish", headers=ADMIN, json={})
    assert res.status_code == 200
    detail = res.json()
    assert detail["configVersion"] == 1 and detail["configState"] == "published"
    again = client.post(f"{CFG}/categories/{cat['category_id']}/publish", headers=ADMIN, json={})
    assert again.status_code == 409 and again.json()["code"] == "nothing_to_publish"


# ---- applicant workflow -----------------------------------------------------------------------

def test_applicant_gets_configured_fields_and_cannot_submit_without_required_information(client):
    cat = _make_category(client)
    _publish(client, cat)
    cfg = client.get(f"{API}/applications/categories/{cat['code']}/config", headers=APPLICANT).json()
    assert [f["key"] for f in cfg["infoFields"]] == ["trust_name"]
    assert [r["code"] for r in cfg["requirements"]] == ["CERT"]
    listed = client.get(f"{API}/applications/categories", headers=APPLICANT).json()
    assert cat["code"] in {c["code"] for c in listed}

    app = _draft(client, cat["code"])
    ready = client.get(f"{API}/applications/{app['id']}/readiness", headers=APPLICANT).json()
    codes = {i["code"] for i in ready["mustFix"]}
    assert "missing_information" in codes and "missing_document" in codes and ready["canSubmit"] is False

    blocked = client.post(f"{API}/applications/{app['id']}/submit", headers=APPLICANT, json=CONFIRM)
    assert blocked.status_code == 422 and blocked.json()["code"] == "not_ready"

    saved = client.patch(f"{API}/applications/{app['id']}", headers=APPLICANT, json={"info_values": {"trust_name": "Alpha Trust"}})
    assert saved.status_code == 200 and saved.json()["infoFields"][0]["value"] == "Alpha Trust"
    _upload(client, app["id"], "CERT", "Institution Name: Alpha\nIssue Date: 2025-01-10")
    ready = client.get(f"{API}/applications/{app['id']}/readiness", headers=APPLICANT).json()
    assert ready["mustFix"] == []


def test_unpublished_or_inactive_category_is_not_offered_or_creatable(client):
    cat = _make_category(client)  # never published, inactive
    listed = client.get(f"{API}/applications/categories", headers=APPLICANT).json()
    assert cat["code"] not in {c["code"] for c in listed}
    res = client.post(
        f"{API}/applications",
        headers=APPLICANT,
        json={"category_code": cat["code"], "institution_name": "Config Institute", "program_name": "x", "academic_year": "2025-26", "save_as_draft": True},
    )
    assert res.status_code == 422 and res.json()["code"] == "category_unavailable"


def test_only_published_rules_of_the_applications_category_run_and_results_carry_versions(client):
    fail_rule = _rule_def({"type": "date_not_expired", "field": "valid_until"})
    one = _make_category(client, rule=fail_rule)
    two = _make_category(client)  # same requirement code, no rules
    # A draft (never activated) rule must not run either.
    client.post(
        f"{CFG}/requirements/{one['requirement_id']}/rules",
        headers=ADMIN,
        json={"title": "Draft only", "definition": _rule_def({"type": "field_present", "field": "address"})},
    )
    _publish(client, one)
    _publish(client, two)

    app_one = _draft(client, one["code"], trust_name="T")
    _upload(client, app_one["id"], "CERT", "Institution Name: Alpha\nValid Until: 2001-01-01")
    checks = _checks(client, app_one["id"])
    assert [c["title"] for c in checks] == ["Certificate check"]  # the draft rule is absent
    assert checks[0]["state"] == "failed"
    assert checks[0]["ruleVersion"] == 1 and checks[0]["configVersion"] == 1 and checks[0]["documentVersion"] == 1

    app_two = _draft(client, two["code"], trust_name="T")
    _upload(client, app_two["id"], "CERT", "Institution Name: Alpha\nValid Until: 2001-01-01")
    assert _checks(client, app_two["id"]) == []  # a rule on one category never touches another


def test_missing_value_is_unable_to_evaluate_not_failed(client):
    cat = _make_category(client, rule=_rule_def({"type": "date_not_expired", "field": "valid_until"}))
    _publish(client, cat)
    app = _draft(client, cat["code"], trust_name="T")
    _upload(client, app["id"], "CERT", "Institution Name: Alpha")
    state = _checks(client, app["id"])[0]["state"]
    assert state in ("unable_to_evaluate", "pending") and state != "failed"


def test_existing_application_keeps_its_configuration_after_a_new_publish(client):
    cat = _make_category(client, rule=_rule_def({"type": "date_not_expired", "field": "valid_until"}))
    _publish(client, cat)
    app = _draft(client, cat["code"], trust_name="T")
    assert app["configVersion"] == 1

    client.post(f"{CFG}/rules/{cat['rule_id']}/deactivate", headers=ADMIN)
    res = client.post(f"{CFG}/categories/{cat['category_id']}/publish", headers=ADMIN, json={})
    assert res.json()["configVersion"] == 2

    _upload(client, app["id"], "CERT", "Institution Name: Alpha\nValid Until: 2001-01-01")
    view = client.get(f"{API}/applicant/applications/{app['id']}", headers=APPLICANT).json()
    assert view["configVersion"] == 1  # still judged by the version it was created under
    assert [c["title"] for c in next(r for r in view["requirements"] if r["code"] == "CERT")["checks"]] == ["Certificate check"]

    fresh = _draft(client, cat["code"], trust_name="T")
    assert fresh["configVersion"] == 2


# ---- authorisation ----------------------------------------------------------------------------

@pytest.mark.parametrize("headers", [APPLICANT, OFFICER])
def test_configuration_endpoints_reject_non_administrators(client, headers):
    cat = _make_category(client)
    assert client.get(f"{CFG}/categories", headers=headers).status_code == 403
    assert client.post(f"{CFG}/categories/{cat['category_id']}/publish", headers=headers, json={}).status_code == 403
    assert (
        client.post(f"{CFG}/requirements/{cat['requirement_id']}/rules", headers=headers, json={"title": "Nope rule"}).status_code
        == 403
    )
    assert client.put(f"{CFG}/categories/{cat['category_id']}/info-fields", headers=headers, json={"fields": []}).status_code == 403


def test_a_requirement_identifier_is_permanent(client):
    cat = _make_category(client)
    res = client.patch(f"{CFG}/requirements/{cat['requirement_id']}", headers=ADMIN, json={"code": "OTHER"})
    assert res.status_code == 422 and res.json()["code"] == "requirement_code_immutable"
    dup = client.post(f"{CFG}/categories/{cat['category_id']}/requirements", headers=ADMIN, json={"code": "CERT", "name": "Again"})
    assert dup.status_code == 409
