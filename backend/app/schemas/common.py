from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class HealthResponse(CamelModel):
    status: str
    environment: str
    database: str
    storage_backend: str
    demo_auth: bool


class EvidenceOut(CamelModel):
    id: str
    description: str
    document_id: str | None = None
    document_name: str | None = None
    page_reference: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None


class FindingOut(CamelModel):
    id: str
    title: str
    description: str
    severity: str
    status: str
    outcome: str
    rule_id: str | None = None
    rule_name: str | None = None
    rule_version: str | None = None
    handbook_ref: str | None = None
    evidence: list[EvidenceOut] = Field(default_factory=list)
    created_at: datetime


class DocumentRequirementOut(CamelModel):
    id: str
    code: str
    name: str
    mandatory: bool
    status: str
    allowed_types: list[str]


class DocumentOut(CamelModel):
    id: str
    name: str
    requirement_code: str
    file_name: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime
    version: int
    status: str
    page_count: int | None = None
    extraction_status: str | None = None
    content_kind: str | None = None
    predicted_category: str | None = None
    selected_category: str | None = None
    category_mismatch: bool = False
    latest_extraction_run_id: str | None = None


class ExtractedFieldOut(CamelModel):
    id: str
    field_name: str
    value: str
    raw_value: str | None = None
    normalized_value: str | None = None
    confidence: float | None
    ocr_confidence: float | None = None
    page_number: int | None = None
    page_reference: str | None
    bbox: dict[str, float] | None = None
    coordinate_space: str | None = None
    method: str | None = None
    review_status: str | None = None
    is_conflict: bool = False
    candidate_values: list[dict[str, Any]] = Field(default_factory=list)
    unit: str | None = None
    source_document_id: str
    source_document_name: str
    extraction_run_id: str | None = None
    corrected_value: str | None = None


class ReconciliationValueOut(CamelModel):
    document_id: str
    document_name: str
    value: str
    normalized_value: str | None = None
    page: str | None = None
    page_number: int | None = None
    extracted_field_id: str | None = None
    evidence_snippet: str | None = None


class DiscrepancyOut(CamelModel):
    id: str
    field_name: str
    outcome: str
    values: list[ReconciliationValueOut] = Field(default_factory=list)
    severity: str
    status: str
    title: str | None = None
    description: str | None = None
    match_kind: str | None = None
    original_outcome: str | None = None
    resolution_reason: str | None = None
    resolved_at: datetime | None = None
    fingerprint: str | None = None


class ReconciliationRunOut(CamelModel):
    id: str
    application_id: str
    validation_run_id: str | None = None
    status: str
    trigger: str
    engine_version: str
    input_fingerprint: str
    summary: dict[str, Any] = Field(default_factory=dict)
    items: list[DiscrepancyOut] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None


class ReconciliationResolveIn(BaseModel):
    status: str  # resolved | waived | accepted
    reason: str


class VerificationOut(CamelModel):
    id: str
    claim: str
    status: str
    source: str
    detail: str
    checked_at: datetime | None


class ReviewNoteOut(CamelModel):
    id: str
    author: str
    role: str
    content: str
    created_at: datetime


class AuditEventOut(CamelModel):
    id: str
    action: str
    actor: str
    timestamp: datetime
    detail: str


class ApplicationSummaryOut(CamelModel):
    id: str
    application_number: str
    institution_id: str
    institution_name: str
    category: str
    category_code: str
    submitted_at: datetime | None
    status: str
    priority: str
    deficiency_count: int
    finding_count: int
    requires_manual_review: bool
    priority_score: int | None = None
    assigned_officer: str | None = None


class ApplicationDetailOut(ApplicationSummaryOut):
    academic_year: str
    program_name: str
    contact_email: str
    requirements: list[DocumentRequirementOut] = Field(default_factory=list)
    documents: list[DocumentOut] = Field(default_factory=list)
    extracted_fields: list[ExtractedFieldOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)
    discrepancies: list[DiscrepancyOut] = Field(default_factory=list)
    verifications: list[VerificationOut] = Field(default_factory=list)
    review_notes: list[ReviewNoteOut] = Field(default_factory=list)
    audit_events: list[AuditEventOut] = Field(default_factory=list)
    validation_run_id: str | None = None
    validation_run_status: str | None = None


class ApplicationCreateIn(BaseModel):
    category_code: str
    program_name: str
    academic_year: str


class ValidationRunOut(CamelModel):
    validation_run_id: str
    status: str
    findings: list[FindingOut] = Field(default_factory=list)


class UploadResultOut(CamelModel):
    document_id: str
    validation_run_id: str | None = None
    extraction_run_id: str | None = None
    extraction_status: str | None = None
    findings: list[FindingOut] = Field(default_factory=list)
    file_checks: dict[str, Any]
