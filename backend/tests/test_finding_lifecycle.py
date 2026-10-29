"""Finding lifecycle (S3) and multi-finding clarifications (S4): validated, recorded, carried."""

from __future__ import annotations

from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
API = "/api/v1"
FORBIDDEN = {"priorityScore", "scoreBreakdown", "ruleCode", "ruleId", "forensicsIndicators", "fingerprint"}


def _create(client):
    res = client.post(
        f"{API}/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Lifecycle Institute",
            "program_name": "B.Tech CSE",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _upload(client, app_id, req, body: bytes, name):
    res = client.post(
        f"{API}/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": (name, body, "text/plain")},
        data={"requirement_code": req},
    )
    assert res.status_code == 200, res.text


def _findings(client, app_id):
    res = client.get(f"{API}/applications/{app_id}", headers=OFFICER)
    assert res.status_code == 200, res.text
    return res.json()["findings"]


def _review(client, app_id):
    return client.get(f"{API}/applications/{app_id}/scrutiny-review", headers=OFFICER).json()


def _transition(client, finding_id, status, reason="", headers=OFFICER):
    return client.post(
        f"{API}/findings/{finding_id}/transition",
        headers=headers,
        json={"status": status, "reason": reason},
    )


def _history(client, finding_id):
    res = client.get(f"{API}/findings/{finding_id}/history", headers=OFFICER)
    assert res.status_code == 200, res.text
    return res.json()


def _case_with_findings(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n", "expired_affidavit.txt")
    client.post(f"{API}/applications/{app_id}/scrutiny/start", headers=OFFICER)
    findings = _findings(client, app_id)
    assert findings, "fixture expects the expired affidavit to produce findings"
    return app_id, findings


def test_lifecycle_moves_are_validated_and_recorded(client):
    app_id, findings = _case_with_findings(client)
    fid = findings[0]["id"]

    assert _transition(client, fid, "under_review").status_code == 200
    # needs a written reason
    short = _transition(client, fid, "clarification_requested")
    assert short.status_code == 422 and short.json()["code"] == "reason_required"
    assert _transition(client, fid, "clarification_requested", "Need the corrected affidavit").status_code == 200

    # system-only and illegal edges are refused
    assert _transition(client, fid, "superseded", "x" * 10).status_code == 422
    closed = _transition(client, fid, "resolved", "Checked the original document")
    assert closed.status_code == 200
    illegal = _transition(client, fid, "open", "go back")
    assert illegal.status_code == 422 and illegal.json()["code"] == "invalid_finding_transition"
    assert _transition(client, fid, "reopened", "Seen a new discrepancy").status_code == 200

    trail = [(h["fromStatus"], h["toStatus"]) for h in _history(client, fid)]
    assert trail == [
        ("open", "under_review"),
        ("under_review", "clarification_requested"),
        ("clarification_requested", "resolved"),
        ("resolved", "reopened"),
    ]
    assert all(h["actorRole"] == "officer" and h["actorName"] for h in _history(client, fid))


def test_applicants_cannot_move_findings(client):
    _, findings = _case_with_findings(client)
    res = _transition(client, findings[0]["id"], "resolved", "I fixed it myself", headers=APPLICANT)
    assert res.status_code == 403


def test_active_states_still_count_as_open_but_expose_their_lifecycle(client):
    app_id, _ = _case_with_findings(client)
    before = _review(client, app_id)
    issue = next(
        i for g in before["issueGroups"] for i in g["issues"] if i["status"] == "open" and i["findingIds"]
    )
    fid = issue["findingIds"][0]
    assert _transition(client, fid, "under_review").status_code == 200
    after = _review(client, app_id)
    assert after["openIssueCount"] == before["openIssueCount"], "under review is still unresolved"
    lifecycles = {
        i["lifecycleStatus"]
        for g in after["issueGroups"]
        for i in g["issues"]
        if fid in i["findingIds"]
    }
    assert lifecycles == {"under_review"}

    assert _transition(client, fid, "resolved", "Verified against the source").status_code == 200
    closed = _review(client, app_id)
    assert closed["openIssueCount"] < before["openIssueCount"]


def test_one_clarification_links_every_selected_finding(client):
    app_id, findings = _case_with_findings(client)
    # add a second, different issue so the request really covers several findings
    _upload(client, app_id, "LAND_OWNERSHIP", b"Institution Name: Different Trust\n", "land.txt")
    findings = _findings(client, app_id)
    ids = list(dict.fromkeys(f["id"] for f in findings))[:3]
    assert len(ids) >= 2, "fixture needs at least two findings"

    res = client.post(
        f"{API}/applications/{app_id}/scrutiny/clarification",
        headers=OFFICER,
        json={"title": "Please correct the listed items", "description": "See the items below.", "finding_ids": ids},
    )
    assert res.status_code == 200, res.text
    by_id = {f["id"]: f for f in _findings(client, app_id)}
    assert all(by_id[i]["status"] == "clarification_requested" for i in ids), "every linked finding moves"

    view = client.get(f"{API}/applicant/applications/{app_id}", headers=APPLICANT).json()
    notice = view["deficiencies"][0]
    assert len(notice["linkedItems"]) >= 2
    assert all(i["documentName"] and i["summary"] for i in notice["linkedItems"])
    assert not (FORBIDDEN & set(str(view).replace("'", " ").replace(",", " ").split()))

    answered = client.post(
        f"{API}/deficiencies/{notice['id']}/respond",
        headers=APPLICANT,
        json={"response": "Uploaded corrected documents for each item."},
    )
    assert answered.status_code == 200, answered.text
    by_id = {f["id"]: f for f in _findings(client, app_id)}
    assert all(by_id[i]["status"] == "under_review" for i in ids), "answered items return to the officer"


def test_clarification_rejects_findings_from_another_application(client):
    app_id, _ = _case_with_findings(client)
    other_id, other_findings = _case_with_findings(client)
    res = client.post(
        f"{API}/applications/{app_id}/scrutiny/clarification",
        headers=OFFICER,
        json={
            "title": "Please correct this",
            "description": "Details here.",
            "finding_ids": [other_findings[0]["id"]],
        },
    )
    assert res.status_code == 422 and res.json()["code"] == "invalid_finding"


def test_rerun_carries_in_progress_state_and_supersedes_old_rows(client):
    app_id, findings = _case_with_findings(client)
    old_id = findings[0]["id"]
    assert _transition(client, old_id, "under_review").status_code == 200

    rerun = client.post(f"{API}/applications/{app_id}/validation-runs", headers=OFFICER)
    assert rerun.status_code == 200, rerun.text

    now = _findings(client, app_id)
    carried = [f for f in now if f["id"] != old_id and f["status"] == "under_review"]
    assert carried, "an identical issue on the same document keeps its in-progress state"
    last = _history(client, old_id)[-1]
    assert last["toStatus"] == "superseded" and last["actorRole"] == "system"


def test_replacing_a_document_supersedes_findings_about_the_old_version(client):
    app_id, findings = _case_with_findings(client)
    old = next(f for f in findings if "expired" in f["title"].lower())
    assert _transition(client, old["id"], "clarification_requested", "Upload an in-date affidavit").status_code == 200

    _upload(
        client,
        app_id,
        "AFFIDAVIT",
        b"Institution Name: Alpha College\nIssue Date: 2025-01-10\nValid Until: 2027-01-10\n",
        "affidavit_ok.txt",
    )
    trail = _history(client, old["id"])
    assert trail[-1]["toStatus"] == "superseded", trail
    assert not any(
        "expired" in f["title"].lower() and f["status"] in {"open", "under_review", "clarification_requested"}
        for f in _findings(client, app_id)
    )
