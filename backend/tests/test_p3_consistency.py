"""P3 regressions: one status model, consistent dashboard numbers, preserved history."""

from app.models.enums import ApplicationStatus
from app.services import status_model
from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
ADMIN = auth_headers("admin")


def _create(client):
    res = client.post(
        "/api/v1/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Consistency Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _upload(client, app_id, req, body: bytes, name="d.txt"):
    res = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": (name, body, "text/plain")},
        data={"requirement_code": req},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _mismatch_app(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n", "a.txt")
    _upload(client, app_id, "LAND_OWNERSHIP", b"Institution Name: Beta College\n", "b.txt")
    client.post(f"/api/v1/applications/{app_id}/validation-runs", headers=OFFICER)
    return app_id


# ---- status model -----------------------------------------------------------------------


def test_every_status_maps_to_exactly_one_stage():
    for status in ApplicationStatus:
        assert status_model.stage_of(status) in status_model.STAGE_LABELS, status
    # A status we have never heard of must stay visible to officers, not vanish.
    assert status_model.stage_of("something_new") == status_model.STAGE_AWAITING_SCRUTINY


def test_waiting_on_applicant_is_not_in_the_officer_queue():
    for status in ("clarification_required", "deficiency"):
        assert status_model.stage_of(status) not in status_model.OFFICER_QUEUE_STAGES
    for status in ("submitted", "resubmitted", "under_scrutiny", "manual_review"):
        assert status_model.stage_of(status) in status_model.OFFICER_QUEUE_STAGES


# ---- dashboards agree with the lists -----------------------------------------------------


def test_metrics_match_the_application_list(client):
    _create(client)
    clar_app = _create(client)
    client.post(f"/api/v1/applications/{clar_app}/scrutiny/start", headers=OFFICER)
    client.post(
        f"/api/v1/applications/{clar_app}/scrutiny/clarification",
        headers=OFFICER,
        json={"title": "Fix the name", "description": "Please upload a corrected affidavit."},
    )

    apps = client.get("/api/v1/applications", headers=OFFICER).json()
    metrics = client.get("/api/v1/applications/metrics", headers=OFFICER).json()

    assert metrics["total"] == len(apps)
    assert sum(metrics["byStage"].values()) == len(apps)
    for stage in metrics["byStage"]:
        assert metrics["byStage"][stage] == sum(1 for a in apps if a["stage"] == stage)
    by_status: dict[str, int] = {}
    for a in apps:
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
    assert metrics["byStatus"] == by_status
    assert metrics["inOfficerQueue"] == metrics["byStage"]["awaiting_scrutiny"] + metrics["byStage"]["under_scrutiny"]
    # Every row's stage label comes from the same table
    for a in apps:
        assert a["stageLabel"] == metrics["stageLabels"][a["stage"]]
    assert next(a for a in apps if a["id"] == clar_app)["stage"] == "awaiting_applicant"


def test_admin_overview_uses_the_same_numbers_as_the_officer_dashboard(client):
    _create(client)
    officer_view = client.get("/api/v1/applications/metrics", headers=OFFICER).json()
    admin_view = client.get("/api/v1/admin/stats", headers=ADMIN).json()
    assert admin_view["applications"] == officer_view


def test_applicant_and_officer_see_the_same_raw_status(client):
    app_id = _create(client)
    client.post(f"/api/v1/applications/{app_id}/scrutiny/start", headers=OFFICER)
    mine = client.get(f"/api/v1/applicant/applications/{app_id}", headers=APPLICANT).json()
    staff = next(
        a for a in client.get("/api/v1/applications", headers=OFFICER).json() if a["id"] == app_id
    )
    assert mine["status"] == staff["status"] == "under_scrutiny"
    listed = next(
        a
        for a in client.get("/api/v1/applicant/applications", headers=APPLICANT).json()
        if a["id"] == app_id
    )
    assert listed["status"] == staff["status"]


def test_queue_issue_count_equals_the_review_count_and_follows_resolution(client):
    app_id = _mismatch_app(client)

    def summary():
        return next(
            a for a in client.get("/api/v1/applications", headers=OFFICER).json() if a["id"] == app_id
        )

    review = client.get(f"/api/v1/applications/{app_id}/scrutiny-review", headers=OFFICER).json()
    assert review["openIssueCount"] > 0
    assert summary()["findingCount"] == review["openIssueCount"]

    # Resolve one open issue's findings: the queue number must drop with the review.
    issue = next(
        i
        for g in review["issueGroups"]
        for i in g["issues"]
        if i["status"] == "open" and i["findingIds"]
    )
    for fid in issue["findingIds"]:
        res = client.post(
            f"/api/v1/findings/{fid}/resolve",
            headers=OFFICER,
            json={"status": "accepted", "reason": "Reviewed against the original document."},
        )
        assert res.status_code == 200, res.text
    after = client.get(f"/api/v1/applications/{app_id}/scrutiny-review", headers=OFFICER).json()
    assert after["openIssueCount"] == review["openIssueCount"] - 1
    assert summary()["findingCount"] == after["openIssueCount"]


# ---- history is preserved ---------------------------------------------------------------


def test_replacing_a_document_keeps_the_old_version_and_audits_it(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: First College\n", "v1.txt")
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Second College\n", "v2.txt")

    detail = client.get(f"/api/v1/applications/{app_id}", headers=OFFICER).json()
    doc = next(d for d in detail["documents"] if d["requirementCode"] == "AFFIDAVIT")
    assert doc["version"] == 2

    # both versions remain retrievable
    v1 = client.get(f"/api/v1/documents/{doc['id']}/file?version=1", headers=OFFICER)
    v2 = client.get(f"/api/v1/documents/{doc['id']}/file", headers=OFFICER)
    assert v1.status_code == 200 and b"First College" in v1.content
    assert v2.status_code == 200 and b"Second College" in v2.content

    # the applicant sees the previous version listed, not erased
    mine = client.get(f"/api/v1/applicant/applications/{app_id}", headers=APPLICANT).json()
    item = next(r for r in mine["requirements"] if r["code"] == "AFFIDAVIT")
    assert [v["version"] for v in item["document"]["previousVersions"]] == [1]

    audit = client.get(f"/api/v1/admin/audit?application_id={app_id}&limit=200", headers=ADMIN).json()
    assert audit["total"] >= 2


def test_clarification_and_decision_history_survive_resubmission(client):
    app_id = _create(client)
    client.post(f"/api/v1/applications/{app_id}/scrutiny/start", headers=OFFICER)
    first = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/clarification",
        headers=OFFICER,
        json={"title": "Name mismatch", "description": "Upload an affidavit with the registered name."},
    )
    assert first.status_code == 200, first.text
    notice = client.get(f"/api/v1/applications/{app_id}/deficiencies", headers=APPLICANT).json()[0]
    client.post(
        f"/api/v1/deficiencies/{notice['id']}/respond",
        headers=APPLICANT,
        json={"response": "Corrected affidavit uploaded with the registered name."},
    )
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Consistency Institute\n", "fix.txt")
    resub = client.post(
        f"/api/v1/applications/{app_id}/resubmit", headers=APPLICANT, json={"note": "Fixed"}
    )
    assert resub.status_code == 200, resub.text

    # the original notice (and the applicant's answer) is still there, now closed or responded
    notices = client.get(f"/api/v1/applications/{app_id}/deficiencies", headers=OFFICER).json()
    original = next(n for n in notices if n["id"] == notice["id"])
    assert original["applicantResponse"].startswith("Corrected affidavit")

    audit = client.get(f"/api/v1/admin/audit?application_id={app_id}&limit=200", headers=ADMIN).json()
    actions = {e["action"] for e in audit["items"]}
    assert any("clarification" in a for a in actions), actions
    assert any("resubmit" in a for a in actions), actions


def test_admin_cannot_record_scrutiny_decisions(client):
    app_id = _create(client)
    client.post(f"/api/v1/applications/{app_id}/scrutiny/start", headers=OFFICER)
    res = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/decision",
        headers=ADMIN,
        json={"recommend": False, "reason": "Administrators must not decide applications."},
    )
    assert res.status_code == 403
    still = client.get(f"/api/v1/applications/{app_id}", headers=OFFICER).json()
    assert still["status"] == "under_scrutiny"
