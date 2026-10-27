"""Phase 1: Pydantic engine DTOs + AdapterResult addendum fields."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.enums import VerificationSource, VerificationStatus
from app.schemas.engine import (
    ApplicationResultOut,
    DocumentResultOut,
    EvidenceOut,
    ExternalVerificationStatus,
    ExtractedFieldOut,
    FindingOut,
    TriageScoreOut,
    VerificationMode,
    VerificationResultOut,
)
from app.verification_engine.adapters.types import AdapterResult


def _vr(**kwargs) -> VerificationResultOut:
    base = dict(
        status=ExternalVerificationStatus.source_unavailable,
        mode=VerificationMode.REAL,
        official_verification=False,
        provider_name="test",
        timestamp=datetime.now(timezone.utc),
        request_summary="req",
        response_summary="resp",
        scope_of_confirmation="field exists",
    )
    base.update(kwargs)
    return VerificationResultOut(**base)


def test_verification_result_ok():
    vr = _vr()
    assert vr.official_verification is False
    assert vr.mode == VerificationMode.REAL


def test_addendum_b_simulated_cannot_be_official():
    with pytest.raises(ValidationError):
        _vr(mode=VerificationMode.SIMULATED, official_verification=True)


def test_external_status_only_six_literals():
    allowed = {e.value for e in ExternalVerificationStatus}
    assert allowed == {
        "verified",
        "mismatch_detected",
        "expired",
        "verification_pending",
        "source_unavailable",
        "manual_review_required",
    }
    with pytest.raises(ValidationError):
        _vr(status="verified_by_source")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        _vr(status="simulated_result")  # type: ignore[arg-type]


def test_extracted_field_keeps_raw_and_normalized():
    f = ExtractedFieldOut(
        field_name="institution_name",
        value="शासकीय अभियांत्रिकी महाविद्यालय",
        normalized_value="shasakiya abhiyantriki mahavidyalaya",
        source="ocr",
        raw_snippet="Institution: ...",
    )
    assert f.value.startswith("शासकीय")
    assert f.normalized_value is not None


def test_document_result_official_flag_false_when_all_simulated():
    vr = _vr(mode=VerificationMode.SIMULATED, official_verification=False)
    doc = DocumentResultOut(
        document_id="d1",
        requirement_code="FIRE_NOC",
        document_type="FIRE_NOC",
        rule_validation_status="pass",
        external_verification_status=ExternalVerificationStatus.source_unavailable,
        review_status="pending",
        signature_status="not_applicable: scanned",
        findings=[
            FindingOut(
                id="f1",
                rule_id="R1",
                severity="info",
                message="ok",
                evidence=[EvidenceOut(document_id="d1", source="layer1")],
                clause_ref="TODO: fill from handbook",
            )
        ],
        verification_results=[vr],
        official_source_confirmed=True,  # should be corrected by validator
    )
    assert doc.official_source_confirmed is False


def test_application_result_shape():
    app = ApplicationResultOut(
        application_id="a1",
        rule_set_version="v1",
        engine_version="praman-engine-0.1",
        generated_at=datetime.now(timezone.utc),
        documents=[],
        triage_score_breakdown=TriageScoreOut(total=0.0, config_version="t0"),
        overall_status="manual_review_required",
        report_disclaimer="Decision-support output; final decision rests with the competent authority.",
    )
    assert "competent authority" in app.report_disclaimer


def test_adapter_result_rejects_simulated_official():
    with pytest.raises(ValueError, match="official_verification"):
        AdapterResult(
            adapter="fire",
            claim_type="fire",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.SIMULATED_DEV,
            detail="x",
            checked_at=datetime.now(timezone.utc),
            mode="SIMULATED",
            official_verification=True,
        )


def test_adapter_result_simulated_dev_forces_mode():
    r = AdapterResult(
        adapter="fire",
        claim_type="fire",
        status=VerificationStatus.SOURCE_UNAVAILABLE,
        source=VerificationSource.SIMULATED_DEV,
        detail="unavailable",
        checked_at=datetime.now(timezone.utc),
    )
    assert r.mode == "SIMULATED"
    assert r.official_verification is False
