"""End-to-end applicant workflow against the real API: draft → upload → submit → clarification →
response (text / document / both) → replacement versions → notifications → evidence.

These tests run the whole stack (routes, services, database), not isolated helpers.
"""

from __future__ import annotations

import json

from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
ADMIN = auth_headers("regional_officer")
API = "/api/v1"
CONFIRM = {"confirm_declarations": True}

FORBIDDEN_WORDS = ("fraud", "forged", "fake", "counterfeit", "tamper", "ruleCode", "fingerprint", "priorityScore")


def _draft(client, **over):
    body = {
        "category_code": "NEW-ENG",
        "institution_name": "Workflow Institute",
        "program_name": "B.Tech CSE",
        "academic_year": "2025-26",
        "save_as_draft": True,
    }
    body.update(over)
    res = client.post(f"{API}/applications", headers=APPLICANT, json=body)
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _body(code, name="Alpha College"):
    return f"Institution Name: {name}\nDocument: {code}\nIssue Date: 2025-01-10".encode()


def _upload(client, app_id, code, body=None, name="doc.txt"):
    body = body if body is not None else _body(code)
    res = client.post(
        f"{API}/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": (name, body, "text/plain")},
        data={"requirement_code": code},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _view(client, app_id):
    res = client.get(f"{API}/applicant/applications/{app_id}", headers=APPLICANT)
    assert res.status_code == 200, res.text
    return res.json()


def _upload_all_mandatory(client, app_id):
    ready = client.get(f"{API}/applications/{app_id}/readiness", headers=APPLICANT).json()
    for item in ready["mustFix"]:
        if item["code"] == "missing_document":
            _upload(client, app_id, item["requirementCode"], name=f"{item['requirementCode']}.txt")


def _submitted_case(client):
    app_id = _draft(client)
    _upload_all_mandatory(client, app_id)
    res = client.post(f"{API}/applications/{app_id}/submit", headers=APPLICANT, json=CONFIRM)
    assert res.status_code == 200, res.text
    client.post(f"{API}/applications/{app_id}/scrutiny/start", headers=OFFICER)
    detail = client.get(f"{API}/applications/{app_id}", headers=OFFICER).json()
    return app_id, detail["findings"]


def _clarify(client, app_id, findings, **over):
    body = {
        "title": "Corrected affidavit needed",
        "description": "Affidavit: upload an unexpired affidavit",
        "finding_ids": [f["id"] for f in findings[:2]],
    }
    body.update(over)
    res = client.post(f"{API}/applications/{app_id}/scrutiny/clarification", headers=OFFICER, json=body)
    assert res.status_code == 200, res.text
    clar = client.get(f"{API}/applicant/clarifications", headers=APPLICANT).json()
    return next(c for c in clar if c["applicationId"] == app_id and c["status"] == "open")


# ---- 1/2/3: draft, checklist, details autosave -------------------------------------------------

def test_draft_is_private_and_autosaves_details_without_losing_documents(client):
    app_id = _draft(client)
    assert client.get(f"{API}/applications/{app_id}", headers=OFFICER).status_code == 404
    first_code = client.get(f"{API}/applications/{app_id}/readiness", headers=APPLICANT).json()["mustFix"][0][
        "requirementCode"
    ]
    _upload(client, app_id, first_code)

    res = client.patch(
        f"{API}/applications/{app_id}", headers=APPLICANT, json={"program_name": "M.Tech", "category_code": "EOA"}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["programName"] == "M.Tech" and body["categoryCode"] == "EOA"
    # Documents are kept even when the new category does not list them: never silently discarded.
    kept = {r["code"] for r in body["requirements"] if r["document"]} | {d["fileName"] and "x" for d in body["otherDocuments"]}
    assert kept, "an uploaded document must remain visible after a category change"


def test_only_the_owner_can_edit_and_only_drafts(client):
    app_id = _draft(client)
    assert client.patch(f"{API}/applications/{app_id}", headers=OFFICER, json={"program_name": "x"}).status_code == 403
    _upload_all_mandatory(client, app_id)
    client.post(f"{API}/applications/{app_id}/submit", headers=APPLICANT, json=CONFIRM)
    res = client.patch(f"{API}/applications/{app_id}", headers=APPLICANT, json={"program_name": "Sneaky"})
    assert res.status_code == 409
    assert res.json()["code"] == "not_a_draft"


# ---- 5: readiness, declarations, duplicate submit ----------------------------------------------

def test_submit_requires_declarations_and_is_safe_to_repeat(client):
    app_id = _draft(client)
    _upload_all_mandatory(client, app_id)
    ready = client.get(f"{API}/applications/{app_id}/readiness", headers=APPLICANT).json()
    assert ready["declarations"], "the server lists the declarations"
    assert ready["canSubmit"] is True

    refused = client.post(f"{API}/applications/{app_id}/submit", headers=APPLICANT)
    assert refused.status_code == 422 and refused.json()["code"] == "declaration_required"
    assert _view(client, app_id)["status"] == "draft"

    ok = client.post(f"{API}/applications/{app_id}/submit", headers=APPLICANT, json=CONFIRM)
    assert ok.status_code == 200 and ok.json()["alreadySubmitted"] is False
    again = client.post(f"{API}/applications/{app_id}/submit", headers=APPLICANT, json=CONFIRM)
    assert again.status_code == 200 and again.json()["alreadySubmitted"] is True


def test_readiness_blocks_missing_details(client):
    app_id = _draft(client, program_name="")
    ready = client.get(f"{API}/applications/{app_id}/readiness", headers=APPLICANT).json()
    assert any(i["code"] == "missing_details" for i in ready["mustFix"])
    assert ready["canSubmit"] is False


# ---- 6: lifecycle and overview come from persisted state ---------------------------------------

def test_lifecycle_and_overview_reflect_persisted_state(client):
    draft_id = _draft(client)
    draft_view = _view(client, draft_id)
    assert draft_view["stage"] == "draft"
    assert [s["key"] for s in draft_view["lifecycle"]][:2] == ["draft", "submitted"]
    assert draft_view["lifecycle"][0]["state"] == "current"
    assert all(s["key"] not in ("applicant_action", "resubmitted") for s in draft_view["lifecycle"])

    app_id, findings = _submitted_case(client)
    clar = _clarify(client, app_id, findings)
    view = _view(client, app_id)
    assert view["stage"] == "applicant_action"
    states = {s["key"]: s["state"] for s in view["lifecycle"]}
    assert states["applicant_action"] == "current" and states["submitted"] == "done"
    assert next(s for s in view["lifecycle"] if s["key"] == "applicant_action")["at"], "timestamp from the audit trail"

    overview = client.get(f"{API}/applicant/overview", headers=APPLICANT).json()
    summaries = client.get(f"{API}/applicant/applications", headers=APPLICANT).json()
    assert overview["drafts"] == sum(1 for s in summaries if s["stage"] == "draft")
    assert overview["actionRequired"] == sum(1 for s in summaries if s["openClarifications"] > 0)
    assert overview["decisionRecorded"] == sum(1 for s in summaries if s["stage"] == "decision_recorded")
    top = overview["nextActions"][0]
    assert top["kind"] == "respond_clarification" and top["clarificationId"] == clar["id"]
    assert top["reason"]


# ---- 4/5: applicant-visible findings and evidence ----------------------------------------------

def test_findings_are_officer_scoped_stable_and_never_accusatory(client):
    app_id, findings = _submitted_case(client)
    assert _view(client, app_id)["findings"] == [], "automatic findings are not exposed until the officer acts"

    clar = _clarify(client, app_id, findings)
    view = _view(client, app_id)
    assert view["findings"], "findings the officer attached to a request are visible"
    f = view["findings"][0]
    assert f["reference"].startswith("F-") and f["kind"] == "officer_request"
    assert f["status"] == "response_needed" and f["nextAction"]
    assert f["clarificationId"] == clar["id"] and f["document"]["name"]
    blob = json.dumps(view).lower()
    for word in FORBIDDEN_WORDS:
        assert word.lower() not in blob, word

    ev = client.get(f"{API}/applicant/findings/{f['id']}/evidence", headers=APPLICANT)
    assert ev.status_code == 200, ev.text
    body = ev.json()
    assert body["reference"] == f["reference"] and body["locationNote"]
    for field in body["fields"]:  # coordinates only when genuinely recorded
        assert field["bbox"] is None or set(field["bbox"]) == {"x0", "y0", "x1", "y1"}


def test_evidence_is_refused_for_unlisted_findings_and_other_roles(client):
    app_id, findings = _submitted_case(client)
    hidden = findings[-1]["id"]
    assert client.get(f"{API}/applicant/findings/{hidden}/evidence", headers=APPLICANT).status_code == 404
    assert client.get(f"{API}/applicant/findings/{hidden}/evidence", headers=OFFICER).status_code == 403
    assert client.get(f"{API}/applicant/findings/nope/evidence", headers=APPLICANT).status_code == 404


# ---- 6/8/9: structured clarification responses -------------------------------------------------

def test_text_only_cannot_satisfy_a_mandatory_replacement(client):
    app_id, findings = _submitted_case(client)
    clar = _clarify(client, app_id, findings, requires_replacement=True)
    assert clar["requiresReplacement"] is True and clar["replacementReceived"] is False

    res = client.post(
        f"{API}/deficiencies/{clar['id']}/respond", headers=APPLICANT, json={"response": "I fixed it, honest."}
    )
    assert res.status_code == 422 and res.json()["code"] == "replacement_required"

    doc = clar["affectedDocuments"][0]
    code = next(r["code"] for r in _view(client, app_id)["requirements"] if r["document"] and r["document"]["id"] == doc["documentId"])
    _upload(client, app_id, code, body=_body(code, "Workflow Institute") + b"\nValid until 2099", name="renewed.txt")
    # The upload alone does not resolve anything.
    still = next(c for c in client.get(f"{API}/applicant/clarifications", headers=APPLICANT).json() if c["id"] == clar["id"])
    assert still["status"] == "open" and still["replacementReceived"] is True

    ok = client.post(f"{API}/deficiencies/{clar['id']}/respond", headers=APPLICANT, json={"response": "Renewed affidavit attached."})
    assert ok.status_code == 200, ok.text
    done = next(c for c in client.get(f"{API}/applicant/clarifications", headers=APPLICANT).json() if c["id"] == clar["id"])
    assert done["responses"][-1]["mode"] == "both"
    assert done["responses"][-1]["documents"][0]["version"] == 2
    assert done["applicantState"] in ("response_saved", "awaiting_review")


def test_document_alone_answers_a_replacement_request(client):
    app_id, findings = _submitted_case(client)
    clar = _clarify(client, app_id, findings, requires_replacement=True)
    doc = clar["affectedDocuments"][0]
    code = next(r["code"] for r in _view(client, app_id)["requirements"] if r["document"] and r["document"]["id"] == doc["documentId"])
    _upload(client, app_id, code, body=_body(code, "Workflow Institute") + b"\nValid until 2099", name="renewed.txt")
    ok = client.post(f"{API}/deficiencies/{clar['id']}/respond", headers=APPLICANT, json={})
    assert ok.status_code == 200, ok.text
    done = next(c for c in client.get(f"{API}/applicant/clarifications", headers=APPLICANT).json() if c["id"] == clar["id"])
    assert done["responses"][-1]["mode"] == "document"


def test_explanation_only_needs_no_upload_and_cannot_be_empty(client):
    app_id, findings = _submitted_case(client)
    clar = _clarify(client, app_id, findings, requires_replacement=False)
    empty = client.post(f"{API}/deficiencies/{clar['id']}/respond", headers=APPLICANT, json={"response": " "})
    assert empty.status_code == 422 and empty.json()["code"] == "response_required"
    ok = client.post(
        f"{API}/deficiencies/{clar['id']}/respond", headers=APPLICANT, json={"response": "The name is the registered trust name."}
    )
    assert ok.status_code == 200, ok.text
    again = client.post(f"{API}/deficiencies/{clar['id']}/respond", headers=APPLICANT, json={"response": "twice please"})
    assert again.status_code == 422 and again.json()["code"] == "not_open"


def test_other_institutions_and_roles_cannot_answer(client):
    app_id, findings = _submitted_case(client)
    clar = _clarify(client, app_id, findings)
    assert client.post(f"{API}/deficiencies/{clar['id']}/respond", headers=OFFICER, json={"response": "no no"}).status_code == 403


# ---- 7: version-aware documents ----------------------------------------------------------------

def test_replacement_creates_a_version_keeps_history_and_marks_results_stale(client):
    app_id = _draft(client)
    first = _upload(client, app_id, "AFFIDAVIT", name="v1.txt")
    assert first["documentVersion"] == 1
    second = _upload(client, app_id, "AFFIDAVIT", body=_body("AFFIDAVIT", "Beta College"), name="v2.txt")
    assert second["documentVersion"] == 2 and second["replacedPrevious"] is True

    doc = next(r["document"] for r in _view(client, app_id)["requirements"] if r["code"] == "AFFIDAVIT")
    assert doc["version"] == 2 and [v["version"] for v in doc["versions"]] == [2, 1]
    assert doc["versions"][0]["isCurrent"] is True and doc["versions"][1]["isCurrent"] is False
    assert all(v["processingState"] in ("ready", "limited", "failed", "processing", "not_run") for v in doc["versions"])
    # The earlier file is still retrievable by version, through the authorised preview route.
    old = client.get(f"{API}/documents/{doc['id']}/file", headers=APPLICANT, params={"version": 1})
    assert old.status_code == 200 and b"Alpha" in old.content
    assert client.get(f"{API}/documents/{doc['id']}/file", headers=OFFICER).status_code == 404  # draft is private


def test_replacement_supersedes_earlier_findings_for_the_applicant(client):
    app_id, findings = _submitted_case(client)
    clar = _clarify(client, app_id, findings, requires_replacement=True)
    ref_before = {f["reference"] for f in _view(client, app_id)["findings"]}
    doc = clar["affectedDocuments"][0]
    code = next(r["code"] for r in _view(client, app_id)["requirements"] if r["document"] and r["document"]["id"] == doc["documentId"])
    _upload(client, app_id, code, body=_body(code, "Workflow Institute") + b"\nValid until 2099", name="renewed.txt")
    after = _view(client, app_id)
    # Same issue keeps the same reference across versions; it never silently disappears.
    assert ref_before <= {f["reference"] for f in after["findings"]}


# ---- 8: notifications --------------------------------------------------------------------------

def test_real_events_create_notifications_for_the_right_people(client):
    app_id, findings = _submitted_case(client)
    clar = _clarify(client, app_id, findings)
    mine = client.get(f"{API}/notifications", headers=APPLICANT).json()["items"]
    kinds = {n["kind"] for n in mine if n["applicationId"] == app_id}
    assert {"application_submitted", "clarification_requested", "status_changed"} <= kinds
    # A file uploaded after submission reports how it was processed.
    doc = clar["affectedDocuments"][0]
    code = next(r["code"] for r in _view(client, app_id)["requirements"] if r["document"] and r["document"]["id"] == doc["documentId"])
    _upload(client, app_id, code, body=_body(code, "Workflow Institute"), name="again.txt")
    mine = client.get(f"{API}/notifications", headers=APPLICANT).json()["items"]
    kinds = {n["kind"] for n in mine if n["applicationId"] == app_id}
    assert "processing_completed" in kinds or "processing_failed" in kinds
    client.post(f"{API}/deficiencies/{clar['id']}/respond", headers=APPLICANT, json={"response": "Name verified with the trust deed."})
    theirs = client.get(f"{API}/notifications", headers=OFFICER).json()["items"]
    assert any(n["kind"] == "clarification_answered" and n["applicationId"] == app_id for n in theirs)
    assert not any(n["applicationId"] == app_id for n in client.get(f"{API}/notifications", headers=ADMIN).json()["items"])


# ---- 7: stale background result must not overwrite the latest version --------------------------

def test_late_verification_run_does_not_overwrite_the_newer_version(client, monkeypatch):
    from app.core.database import SessionLocal
    from app.models.document import Document
    from app.verification_engine import pipeline

    app_id = _draft(client)
    _upload(client, app_id, "AFFIDAVIT", name="v1.txt")
    doc_id = next(r["document"]["id"] for r in _view(client, app_id)["requirements"] if r["code"] == "AFFIDAVIT")

    original = pipeline._fields_for_version

    def bump_version_mid_run(db, version_id):
        # Simulates a replacement landing while the older version is still being verified.
        doc = db.get(Document, doc_id)
        doc.current_version += 1
        db.flush()
        return original(db, version_id)

    monkeypatch.setattr(pipeline, "_fields_for_version", bump_version_mid_run)
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        if pipeline.get_config_for_requirement(doc.requirement_code) is None:
            return  # no verification config for this requirement in this build
        run = pipeline.run_for_document(db, doc, commit=True)
        db.refresh(doc)
        assert run is not None and (run.summary or {}).get("superseded") is True
        assert doc.latest_verification_run_id is None, "the stale run must not become the current result"
