"""Phase 5: unified scrutiny workflow, scoring, RBAC, resubmit, audit."""

from tests.conftest import auth_headers


def _create_app(client):
    res = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "Workflow CSE",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _upload(client, app_id: str, name: str, body: bytes, req: str):
    res = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": (name, body, "text/plain")},
        data={"requirement_code": req},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_create_starts_submitted_and_validation_moves_workflow(client):
    app = _create_app(client)
    assert app["status"] == "submitted"
    app_id = app["id"]
    _upload(
        client,
        app_id,
        "a.txt",
        b"Institution Name: Workflow College\n",
        "AFFIDAVIT",
    )
    val = client.post(
        f"/api/v1/applications/{app_id}/validation-runs",
        headers=auth_headers("officer"),
    )
    assert val.status_code == 200, val.text
    detail = client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers("officer"),
    ).json()
    assert detail["status"] == "under_scrutiny"
    assert detail["priorityScore"] is not None
    assert detail["scoreBreakdown"]["configVersion"] == "scrutiny-weights-v1"
    assert "disclaimer" in detail["scoreBreakdown"]
    assert detail["scrutinySummary"]
    assert "not" in detail["scrutinySummary"]["disclaimer"].lower()


def test_invalid_transition_rejected(client):
    app = _create_app(client)
    # Cannot recommend directly from submitted without going through scrutiny path properly
    # start_scrutiny from submitted should work
    ok = client.post(
        f"/api/v1/applications/{app['id']}/scrutiny/start",
        headers=auth_headers("officer"),
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "under_scrutiny"

    # Reject without reason fails
    bad = client.post(
        f"/api/v1/applications/{app['id']}/scrutiny/decision",
        headers=auth_headers("officer"),
        json={"reason": "x", "recommend": False},
    )
    assert bad.status_code == 422


def test_clarification_resubmit_and_audit(client):
    app = _create_app(client)
    app_id = app["id"]
    client.post(
        f"/api/v1/applications/{app_id}/scrutiny/start",
        headers=auth_headers("officer"),
    )
    clar = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/clarification",
        headers=auth_headers("officer"),
        json={
            "title": "Fix institution name",
            "description": "Please upload a corrected affidavit with matching name.",
        },
    )
    assert clar.status_code == 200, clar.text
    assert clar.json()["status"] == "clarification_required"
    assert clar.json()["deficiencyCount"] >= 1

    defs = client.get(
        f"/api/v1/applications/{app_id}/deficiencies",
        headers=auth_headers("applicant"),
    ).json()
    assert defs
    notice_id = defs[0]["id"]

    # Applicant cannot clarify
    denied = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/clarification",
        headers=auth_headers("applicant"),
        json={"title": "Nope", "description": "Should be forbidden for applicant role"},
    )
    assert denied.status_code in (401, 403)

    resp = client.post(
        f"/api/v1/deficiencies/{notice_id}/respond",
        headers=auth_headers("applicant"),
        json={"response": "Uploaded corrected affidavit matching the land document."},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "responded"

    _upload(
        client,
        app_id,
        "fixed.txt",
        b"Institution Name: Workflow College\nIssue Date: 01-01-2024\n",
        "AFFIDAVIT",
    )
    resub = client.post(
        f"/api/v1/applications/{app_id}/resubmit",
        headers=auth_headers("applicant"),
        json={"note": "Corrections uploaded and deficiency addressed."},
    )
    assert resub.status_code == 200, resub.text
    assert resub.json()["status"] in {"resubmitted", "processing", "under_scrutiny"}

    detail = client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers("officer"),
    ).json()
    actions = {a["action"] for a in detail["auditEvents"]}
    assert "workflow.clarification_requested" in actions
    assert "workflow.deficiency_responded" in actions
    assert "workflow.resubmitted" in actions


def test_recommend_preserves_findings_and_score_explanation(client):
    app = _create_app(client)
    app_id = app["id"]
    _upload(client, app_id, "a.txt", b"Institution Name: A College\n", "AFFIDAVIT")
    _upload(client, app_id, "b.txt", b"Institution Name: B College\n", "LAND_OWNERSHIP")
    client.post(
        f"/api/v1/applications/{app_id}/validation-runs",
        headers=auth_headers("officer"),
    )
    client.post(
        f"/api/v1/applications/{app_id}/scrutiny/start",
        headers=auth_headers("officer"),
    )
    before = client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers("officer"),
    ).json()
    finding_count_before = before["findingCount"]
    contribs = before["scoreBreakdown"].get("contributions") or []
    assert finding_count_before >= 1 or contribs

    rec = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/decision",
        headers=auth_headers("officer"),
        json={
            "reason": "Officer reviewed mismatches; recommend with noted residual risk.",
            "recommend": True,
        },
    )
    assert rec.status_code == 200, rec.text
    assert rec.json()["status"] == "recommended"
    # Findings remain in history
    assert rec.json()["findingCount"] >= finding_count_before
    assert rec.json()["scrutinySummary"].get("finalDecision") == "recommended"

    # Terminal: further clarification invalid
    again = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/clarification",
        headers=auth_headers("officer"),
        json={"title": "Too late", "description": "Should fail on terminal recommended status"},
    )
    assert again.status_code == 422


def test_applicant_cannot_decide(client):
    app = _create_app(client)
    client.post(
        f"/api/v1/applications/{app['id']}/scrutiny/start",
        headers=auth_headers("officer"),
    )
    denied = client.post(
        f"/api/v1/applications/{app['id']}/scrutiny/decision",
        headers=auth_headers("applicant"),
        json={"reason": "Applicant trying to recommend themselves wrongly", "recommend": True},
    )
    assert denied.status_code in (401, 403)


def test_score_incomplete_processing_not_compliance(client):
    """No validation run → score includes partial_processing_penalty, not a clean pass story."""
    from app.core.database import SessionLocal
    from app.models.application import Application
    from app.services.scoring import compute_scrutiny_score

    app = _create_app(client)
    db = SessionLocal()
    try:
        row = db.query(Application).filter(Application.id == app["id"]).one()
        score = compute_scrutiny_score(db, row)
        assert score.processing_complete is False
        assert any(c.weight_key == "partial_processing_penalty" for c in score.contributions)
        assert "incomplete" in " ".join(score.notes).lower() or "not" in score.to_dict()["disclaimer"].lower()
    finally:
        db.close()
