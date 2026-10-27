from datetime import datetime, timezone

from app.schemas.engine import (
    ApplicationResultOut,
    DocumentResultOut,
    ExternalVerificationStatus,
    TriageScoreOut,
    VerificationMode,
    VerificationResultOut,
)
from app.services.report_service import DECISION_NOTICE, render_report_html
from app.services.serializers import to_application_result_out


def test_disclaimer_when_simulated(client):
    _ = client
    from app.core.database import SessionLocal
    from app.models.application import Application
    from tests.conftest import auth_headers

    # Create via API then fetch report
    res = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={"category_code": "NEW-ENG", "institution_name": "Test Institute of Technology", "program_name": "B.Tech", "academic_year": "2025-26"},
    )
    assert res.status_code in (200, 201)
    app_id = res.json()["id"]
    report = client.get(f"/api/v1/applications/{app_id}/report.json", headers=auth_headers("officer"))
    assert report.status_code == 200
    body = report.json()
    disclaimer = body.get("report_disclaimer") or body.get("reportDisclaimer") or ""
    assert "competent authority" in disclaimer.lower() or "decision-support" in disclaimer.lower()


def test_addendum_d_disclaimer_text():
    vr = VerificationResultOut(
        status=ExternalVerificationStatus.source_unavailable,
        mode=VerificationMode.SIMULATED,
        official_verification=False,
        provider_name="sim",
        timestamp=datetime.now(timezone.utc),
        request_summary="r",
        response_summary="s",
        scope_of_confirmation="fixture",
    )
    doc = DocumentResultOut(
        document_id="d1",
        requirement_code="FIRE_NOC",
        document_type="FIRE_NOC",
        rule_validation_status="pass",
        external_verification_status=ExternalVerificationStatus.source_unavailable,
        review_status="pending",
        signature_status="not_applicable: scanned",
        verification_results=[vr],
        official_source_confirmed=False,
    )
    app = ApplicationResultOut(
        application_id="a1",
        rule_set_version="v1",
        engine_version="e",
        generated_at=datetime.now(timezone.utc),
        documents=[doc],
        triage_score_breakdown=TriageScoreOut(total=0, config_version="t"),
        overall_status="manual_review_required",
        report_disclaimer="IMPORTANT: The following documents were NOT confirmed by any official external source: FIRE_NOC.",
    )
    html = render_report_html(app)
    assert "NOT confirmed by any official" in html
    assert DECISION_NOTICE in html
    assert "[SIMULATED]" in html or "SIMULATED" in html
