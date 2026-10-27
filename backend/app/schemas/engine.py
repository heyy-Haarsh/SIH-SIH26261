"""Pipeline / scrutiny report DTOs (Pydantic v2). Not ORM models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class VerificationMode(str, Enum):
    REAL = "REAL"
    SIMULATED = "SIMULATED"


class ExternalVerificationStatus(str, Enum):
    """Exactly the 6 product-spec literals for report / ApplicationResult status."""

    verified = "verified"
    mismatch_detected = "mismatch_detected"
    expired = "expired"
    verification_pending = "verification_pending"
    source_unavailable = "source_unavailable"
    manual_review_required = "manual_review_required"


class VerificationResultOut(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    status: ExternalVerificationStatus
    mode: VerificationMode
    official_verification: bool
    provider_name: str
    provider_reference_id: Optional[str] = None
    timestamp: datetime
    request_summary: str
    response_summary: str
    scope_of_confirmation: str
    matched_fields: list[str] = []
    mismatched_fields: list[str] = []
    source_url: Optional[str] = None
    raw_evidence_ref: Optional[str] = None

    @model_validator(mode="after")
    def enforce_official_false_for_simulated(self) -> VerificationResultOut:
        if self.mode == VerificationMode.SIMULATED and self.official_verification:
            raise ValueError("official_verification must be False when mode is SIMULATED")
        return self


class ExtractedFieldOut(BaseModel):
    field_name: str
    value: str
    normalized_value: Optional[str] = None
    confidence: Optional[float] = None
    page: Optional[int] = None
    bbox: Optional[list[float]] = None
    source: Literal["text_layer", "ocr", "llm", "filename_metadata"]
    raw_snippet: Optional[str] = None


class EvidenceOut(BaseModel):
    document_id: str
    page: Optional[int] = None
    bbox: Optional[list[float]] = None
    snippet: Optional[str] = None
    original_value: Optional[str] = None
    normalized_value: Optional[str] = None
    source: str


class FindingOut(BaseModel):
    id: str
    rule_id: str
    severity: str
    message: str
    evidence: list[EvidenceOut] = []
    clause_ref: str
    confidence: Optional[float] = None


class SignalScoreOut(BaseModel):
    signal_code: str
    raw_score: float
    weight: float
    contribution: float
    reason: str
    confidence: float
    evidence_region: Optional[str] = None
    interpretation: str = "preliminary indicator requiring human verification"


class TriageScoreOut(BaseModel):
    total: float
    signals: list[SignalScoreOut] = []
    interpretation: str = "preliminary indicator requiring human verification"
    config_version: str


class DocumentResultOut(BaseModel):
    document_id: str
    requirement_code: str
    document_type: str
    rule_validation_status: str
    external_verification_status: ExternalVerificationStatus
    review_status: str
    signature_status: str
    findings: list[FindingOut] = []
    forensic_signals: list[SignalScoreOut] = []
    verification_results: list[VerificationResultOut] = []
    official_source_confirmed: bool = False

    @model_validator(mode="after")
    def derive_official_flag(self) -> DocumentResultOut:
        if self.verification_results:
            self.official_source_confirmed = any(
                v.official_verification for v in self.verification_results
            )
        return self


class ApplicationResultOut(BaseModel):
    application_id: str
    rule_set_version: str
    engine_version: str
    generated_at: datetime
    documents: list[DocumentResultOut] = []
    cross_doc_findings: list[FindingOut] = []
    triage_score_breakdown: TriageScoreOut
    overall_status: str
    report_disclaimer: str
