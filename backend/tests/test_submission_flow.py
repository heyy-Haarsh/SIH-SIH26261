"""Draft → readiness → explicit submit: enforced on the server, idempotent, private until submitted."""

from __future__ import annotations

from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
REGIONAL = auth_headers("regional_officer")
API = "/api/v1"
CONFIRM = {"confirm_declarations": True}

FORBIDDEN_IN_READINESS = {"priorityScore", "scoreBreakdown", "ruleCode", "ruleId", "forensicsIndicators"}


def _draft(client, **overrides):
    body = {
        "category_code": "NEW-ENG",
        "institution_name": "Submission Flow Institute",
        "program_name": "B.Tech IT",
        "academic_year": "2025-26",
        "save_as_draft": True,
    }
    body.update(overrides)
    res = client.post(f"{API}/applications", headers=APPLICANT, json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _upload(client, app_id, code, text=None):
    body = (text or f"Institution Name: Submission Flow Institute\nDocument: {code}\nIssue Date: 2025-01-10").encode()
    return client.post(
        f"{API}/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": (f"{code.lower()}.txt", body, "text/plain")},
        data={"requirement_code": code},
    )


def _mandatory_codes(client):
    cats = client.get(f"{API}/applications/categories", headers=APPLICANT).json()
    cat = next(c for c in cats if c["code"] == "NEW-ENG")
    return [d["code"] for d in cat["requiredDocuments"] if d.get("mandatory", True)]


def _staff_numbers(client, headers):
    return {a["applicationNumber"] for a in client.get(f"{API}/applications", headers=headers).json()}


def test_draft_is_private_and_not_delegated(client):
    before = client.get(f"{API}/applications/metrics", headers=REGIONAL).json()["total"]
    draft = _draft(client)
    assert draft["status"] == "draft"
    assert draft["submittedAt"] is None

    assert draft["applicationNumber"] not in _staff_numbers(client, OFFICER)
    assert draft["applicationNumber"] not in _staff_numbers(client, REGIONAL)
    assert client.get(f"{API}/applications/{draft['id']}", headers=OFFICER).status_code == 404
    assert client.get(f"{API}/applications/metrics", headers=REGIONAL).json()["total"] == before

    mine = client.get(f"{API}/applicant/applications/{draft['id']}", headers=APPLICANT).json()
    assert mine["status"] == "draft"


def test_default_create_still_submits_immediately_for_legacy_clients(client):
    res = client.post(
        f"{API}/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Legacy Client Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "submitted"


def test_readiness_lists_every_missing_mandatory_document_and_blocks_submit(client):
    draft = _draft(client)
    readiness = client.get(f"{API}/applications/{draft['id']}/readiness", headers=APPLICANT).json()
    assert readiness["isDraft"] is True and readiness["canSubmit"] is False
    missing = {i["requirementCode"] for i in readiness["mustFix"] if i["code"] == "missing_document"}
    assert missing == set(_mandatory_codes(client))
    assert readiness["limitations"], "limitations must always be stated"
    assert not (FORBIDDEN_IN_READINESS & set(str(readiness).replace("'", " ").split()))

    res = client.post(f"{API}/applications/{draft['id']}/submit", headers=APPLICANT, json=CONFIRM)
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "not_ready"
    still = client.get(f"{API}/applicant/applications/{draft['id']}", headers=APPLICANT).json()
    assert still["status"] == "draft"


def test_submit_hands_over_to_scrutiny_exactly_once(client):
    draft = _draft(client)
    for code in _mandatory_codes(client):
        up = _upload(client, draft["id"], code)
        assert up.status_code == 200, up.text

    # uploading while a draft must not move it into scrutiny or make it visible to staff
    mid = client.get(f"{API}/applicant/applications/{draft['id']}", headers=APPLICANT).json()
    assert mid["status"] == "draft"
    assert draft["applicationNumber"] not in _staff_numbers(client, REGIONAL)

    readiness = client.get(f"{API}/applications/{draft['id']}/readiness", headers=APPLICANT).json()
    assert readiness["mustFix"] == [], readiness
    assert readiness["canSubmit"] is True

    first = client.post(f"{API}/applications/{draft['id']}/submit", headers=APPLICANT, json=CONFIRM)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["alreadySubmitted"] is False
    assert body["status"] in {"under_scrutiny", "processing", "submitted"}
    assert body["submittedAt"]

    second = client.post(f"{API}/applications/{draft['id']}/submit", headers=APPLICANT, json=CONFIRM)
    assert second.status_code == 200, second.text
    assert second.json()["alreadySubmitted"] is True
    assert second.json()["submittedAt"] == body["submittedAt"]

    # visible to staff, assigned to an officer, and the submit was audited once
    assert draft["applicationNumber"] in _staff_numbers(client, REGIONAL)
    detail = client.get(f"{API}/applications/{draft['id']}", headers=REGIONAL).json()
    assert detail["assignedOfficer"]
    audit = client.get(
        f"{API}/admin/audit",
        headers=REGIONAL,
        params={"application_number": draft["applicationNumber"], "action": "application.submitted"},
    ).json()
    assert audit["total"] == 1


def test_only_the_owning_institution_can_submit(client):
    draft = _draft(client)
    res = client.post(f"{API}/applications/{draft['id']}/submit", headers=OFFICER)
    assert res.status_code == 403
    res = client.get(f"{API}/applications/{draft['id']}/readiness", headers=OFFICER)
    assert res.status_code == 403
