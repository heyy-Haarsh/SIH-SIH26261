"""In-app notifications: emitted by real workflow events, private to the recipient."""

from __future__ import annotations

from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
REGIONAL = auth_headers("regional_officer")
API = "/api/v1"
CONFIRM = {"confirm_declarations": True}


def _inbox(client, headers, **params):
    res = client.get(f"{API}/notifications", headers=headers, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _kinds_for(client, headers, application_id):
    return [n["kind"] for n in _inbox(client, headers)["items"] if n["applicationId"] == application_id]


def _legacy_submitted_app(client):
    res = client.post(
        f"{API}/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Notification Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_assignment_notifies_the_assigned_officer_only(client):
    app_id = _legacy_submitted_app(client)
    assert "case_assigned" in _kinds_for(client, OFFICER, app_id)
    assert "case_assigned" not in _kinds_for(client, APPLICANT, app_id)
    assert _inbox(client, OFFICER)["unreadCount"] >= 1


def test_clarification_cycle_notifies_each_side(client):
    app_id = _legacy_submitted_app(client)
    client.post(f"{API}/applications/{app_id}/scrutiny/start", headers=OFFICER)
    res = client.post(
        f"{API}/applications/{app_id}/scrutiny/clarification",
        headers=OFFICER,
        json={"title": "Upload the corrected affidavit", "description": "The name does not match."},
    )
    assert res.status_code == 200, res.text
    assert "clarification_requested" in _kinds_for(client, APPLICANT, app_id)

    notice = client.get(f"{API}/applicant/applications/{app_id}", headers=APPLICANT).json()["deficiencies"][0]
    answered = client.post(
        f"{API}/deficiencies/{notice['id']}/respond",
        headers=APPLICANT,
        json={"response": "We uploaded the corrected affidavit."},
    )
    assert answered.status_code == 200, answered.text
    assert "clarification_answered" in _kinds_for(client, OFFICER, app_id)

    resub = client.post(f"{API}/applications/{app_id}/resubmit", headers=APPLICANT, json={"note": "done"})
    assert resub.status_code == 200, resub.text
    assert "applicant_resubmitted" in _kinds_for(client, OFFICER, app_id)


def test_decision_notifies_the_applicant_without_claiming_an_outcome(client):
    app_id = _legacy_submitted_app(client)
    client.post(f"{API}/applications/{app_id}/scrutiny/start", headers=OFFICER)
    res = client.post(
        f"{API}/applications/{app_id}/scrutiny/decision",
        headers=OFFICER,
        json={"recommend": False, "reason": "Mandatory documents are missing."},
    )
    assert res.status_code == 200, res.text
    notes = [
        n
        for n in _inbox(client, APPLICANT)["items"]
        if n["kind"] == "decision_recorded" and n["applicationId"] == app_id
    ]
    assert notes and "approved" not in notes[0]["title"].lower()


def test_submit_notifies_applicant_and_officer_once(client):
    draft = client.post(
        f"{API}/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Draft Notification Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
            "save_as_draft": True,
        },
    ).json()
    assert _kinds_for(client, OFFICER, draft["id"]) == []  # a draft never reaches staff
    cats = client.get(f"{API}/applications/categories", headers=APPLICANT).json()
    for d in next(c for c in cats if c["code"] == "NEW-ENG")["requiredDocuments"]:
        if d.get("mandatory", True):
            client.post(
                f"{API}/applications/{draft['id']}/documents",
                headers=APPLICANT,
                files={"file": ("a.txt", b"Institution Name: Draft Notification Institute", "text/plain")},
                data={"requirement_code": d["code"]},
            )
    assert client.post(f"{API}/applications/{draft['id']}/submit", headers=APPLICANT, json=CONFIRM).status_code == 200
    assert "application_submitted" in _kinds_for(client, APPLICANT, draft["id"])
    assert "case_assigned" in _kinds_for(client, OFFICER, draft["id"])
    client.post(f"{API}/applications/{draft['id']}/submit", headers=APPLICANT, json=CONFIRM)
    assert _kinds_for(client, APPLICANT, draft["id"]).count("application_submitted") == 1


def test_read_state_and_privacy(client):
    app_id = _legacy_submitted_app(client)
    inbox = _inbox(client, OFFICER)
    target = next(n for n in inbox["items"] if n["applicationId"] == app_id)
    assert target["isRead"] is False and target["link"].endswith(app_id)

    # another user cannot read or mark it
    assert client.post(f"{API}/notifications/{target['id']}/read", headers=APPLICANT).status_code == 404
    assert client.post(f"{API}/notifications/{target['id']}/read", headers=REGIONAL).status_code == 404

    before = inbox["unreadCount"]
    assert client.post(f"{API}/notifications/{target['id']}/read", headers=OFFICER).json()["isRead"] is True
    assert _inbox(client, OFFICER)["unreadCount"] == before - 1
    assert all(not n["isRead"] for n in _inbox(client, OFFICER, unread_only="true")["items"])

    assert client.post(f"{API}/notifications/read-all", headers=OFFICER).status_code == 200
    assert _inbox(client, OFFICER)["unreadCount"] == 0
