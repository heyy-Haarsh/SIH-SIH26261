from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    app_version: str = "0.1.0"
    max_upload_mb: int | None = None
    auto_extract_on_upload: bool | None = None
    enable_live_verification: bool | None = None
    enable_nominatim_geocode: bool | None = None
    limitations: list[str] = Field(default_factory=list)


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


class DocumentCheckOut(CamelModel):
    """Plain-language upload pre-check (type match + clarity). Not an authenticity result."""

    type_match: str  # matched | mismatch | unclear | not_checked
    type_match_message: str
    expected_type: str
    detected_type: str | None = None
    clarity: str  # clear | unclear | unreadable | not_checked
    clarity_message: str
    language_note: str | None = None
    needs_attention: bool = False


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
    # Phase 7 three-layer statuses (independent; L1 pass ≠ authenticity)
    rule_validation_status: str | None = None
    external_verification_status: str | None = None
    review_status: str | None = None
    latest_verification_run_id: str | None = None
    document_check: DocumentCheckOut | None = None


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


class ForensicsEvidenceOut(CamelModel):
    id: str
    description: str
    document_id: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    page_reference: str | None = None
    detail: str | None = None


class ForensicsIndicatorOut(CamelModel):
    id: str
    document_id: str | None = None
    code: str
    risk_class: str
    original_risk_class: str | None = None
    severity: str
    status: str
    verification_status: str
    title: str
    description: str
    affected_pages: list[int] = Field(default_factory=list)
    evidence: list[ForensicsEvidenceOut] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    resolution_reason: str | None = None
    resolved_at: datetime | None = None
    fingerprint: str | None = None


class ForensicsRunOut(CamelModel):
    id: str
    application_id: str
    validation_run_id: str | None = None
    status: str
    trigger: str
    engine_version: str
    input_fingerprint: str
    summary: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    indicators: list[ForensicsIndicatorOut] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None


class ForensicsResolveIn(BaseModel):
    status: str
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
    # Open issues as the scrutiny review counts them (not the raw rule-finding rows).
    finding_count: int
    stage: str = "awaiting_scrutiny"
    stage_label: str = "Awaiting scrutiny"
    requires_manual_review: bool
    priority_score: int | None = None
    score_config_version: str | None = None
    assigned_officer: str | None = None


class DeficiencyOut(CamelModel):
    id: str
    application_id: str
    application_number: str | None = None
    title: str
    description: str
    status: str
    finding_id: str | None = None
    due_date: date | None = None
    applicant_response: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ApplicationDetailOut(ApplicationSummaryOut):
    academic_year: str
    program_name: str
    contact_email: str
    requirements: list[DocumentRequirementOut] = Field(default_factory=list)
    documents: list[DocumentOut] = Field(default_factory=list)
    extracted_fields: list[ExtractedFieldOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)
    discrepancies: list[DiscrepancyOut] = Field(default_factory=list)
    forensics_indicators: list[ForensicsIndicatorOut] = Field(default_factory=list)
    forensics_limitations: list[str] = Field(default_factory=list)
    deficiencies: list[DeficiencyOut] = Field(default_factory=list)
    verifications: list[VerificationOut] = Field(default_factory=list)
    document_verification_runs: list[dict[str, Any]] = Field(default_factory=list)
    review_notes: list[ReviewNoteOut] = Field(default_factory=list)
    audit_events: list[AuditEventOut] = Field(default_factory=list)
    validation_run_id: str | None = None
    validation_run_status: str | None = None
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    scrutiny_summary: dict[str, Any] = Field(default_factory=dict)
    last_transition_at: datetime | None = None
    last_transition_note: str | None = None


class WorkflowClarificationIn(BaseModel):
    title: str
    description: str
    finding_ids: list[str] = Field(default_factory=list)
    # Officer states whether a replacement file is mandatory; the server enforces it on response.
    requires_replacement: bool = False
    due_date: date | None = None


class WorkflowDecisionIn(BaseModel):
    reason: str
    recommend: bool = True


class WorkflowNoteIn(BaseModel):
    content: str


class WorkflowResubmitIn(BaseModel):
    note: str = ""


class DeficiencyRespondIn(BaseModel):
    # May be empty when a replacement document alone answers the request (the server decides).
    response: str = ""


class FindingResolveIn(BaseModel):
    status: str
    reason: str


class FindingTransitionIn(BaseModel):
    status: str
    reason: str = ""


class FindingTransitionOut(CamelModel):
    id: str
    finding_id: str
    from_status: str
    to_status: str
    actor_name: str
    actor_role: str
    reason: str = ""
    created_at: datetime


class ApplicationCategoryBriefOut(CamelModel):
    """Active categories an applicant may choose when creating an application."""

    code: str
    name: str
    description: str = ""
    required_documents: list[dict[str, Any]] = Field(default_factory=list)
    config_version: int | None = None
    info_field_count: int = 0
    mandatory_count: int = 0
    optional_count: int = 0
    available: bool = True


class ApplicationCreateIn(BaseModel):
    category_code: str
    institution_name: str = Field(min_length=1, max_length=255)
    program_name: str
    academic_year: str
    # The applicant UI saves a private draft and submits explicitly. Defaults to False so
    # scripted/legacy clients keep their immediate-submit behaviour.
    save_as_draft: bool = False
    # Values for the category's configured information fields, keyed by field key.
    info_values: dict[str, Any] = Field(default_factory=dict)

    @field_validator("institution_name")
    @classmethod
    def _clean_institution_name(cls, v: str) -> str:
        cleaned = " ".join((v or "").split())
        if len(cleaned) < 3:
            raise ValueError("Institution name must be at least 3 characters.")
        if not any(ch.isalpha() for ch in cleaned):
            raise ValueError("Institution name must contain letters.")
        return cleaned

    @field_validator("program_name", "academic_year")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    @model_validator(mode="after")
    def _require_details_unless_draft(self) -> "ApplicationCreateIn":
        # A draft may be saved before every detail is known (autosave); submission and
        # readiness still require them, so nothing incomplete can reach an officer.
        if not self.save_as_draft:
            for name in ("program_name", "academic_year"):
                if not getattr(self, name):
                    raise ValueError(f"{name}: This field is required.")
        return self


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
    # Explicit pipeline honesty — file accept ≠ extraction/validation success
    pipeline_ok: bool = True
    pipeline_warnings: list[str] = Field(default_factory=list)
    document_check: DocumentCheckOut | None = None
    document_version: int | None = None
    replaced_previous: bool = False


class UploadPolicyOut(CamelModel):
    """Limits the client validates against before sending a file (server still enforces)."""

    max_upload_mb: int
    max_upload_bytes: int
    allowed_extensions: list[str]
    ocr_available: bool
    ocr_languages: list[str]
    marathi_supported: bool
    ocr_message: str


# ---- Applicant-facing view (no extracted fields, scores, forensics or technical codes) ----


class ApplicantDocumentVersionOut(CamelModel):
    version: int
    file_name: str
    uploaded_at: datetime
    size_bytes: int
    is_current: bool = False
    # ready | limited | failed | processing | not_run — from the extraction run for THIS version.
    processing_state: str = "not_run"
    processing_message: str = ""
    # Open officer findings that were recorded against this version (history, not a verdict).
    officer_items: int = 0


class ApplicantDocumentOut(CamelModel):
    id: str
    file_name: str
    version: int
    uploaded_at: datetime
    size_bytes: int
    mime_type: str = ""
    page_count: int | None = None
    document_check: DocumentCheckOut | None = None
    previous_versions: list[ApplicantDocumentVersionOut] = Field(default_factory=list)
    versions: list[ApplicantDocumentVersionOut] = Field(default_factory=list)
    processing_state: str = "not_run"
    processing_message: str = ""
    # True while results from an earlier version are being replaced by a re-check.
    reverification_pending: bool = False


class ApplicantCheckOut(CamelModel):
    """One configured automated check on a document, in the institution's terms."""

    title: str
    meaning: str = ""
    # passed | failed | manual_review | unable_to_evaluate | pending | source_unavailable
    state: str
    state_label: str
    message: str = ""
    document_version: int | None = None
    rule_version: int | None = None
    config_version: int | None = None


class ApplicantRequirementOut(CamelModel):
    code: str
    name: str
    mandatory: bool
    allowed_types: list[str]
    upload_status: str  # not_uploaded | uploaded | replaced | needs_attention
    upload_status_label: str
    document: ApplicantDocumentOut | None = None
    description: str = ""
    max_size_mb: int | None = None
    checks: list[ApplicantCheckOut] = Field(default_factory=list)


class ApplicantLinkedItemOut(CamelModel):
    """One item a clarification covers, in plain words (no rule codes, scores or internals)."""

    document_name: str
    summary: str


class ApplicantResponseEntryOut(CamelModel):
    id: str
    mode: str  # text | document | both
    text: str
    documents: list[dict] = Field(default_factory=list)
    created_at: datetime


class ApplicantAffectedDocumentOut(CamelModel):
    document_id: str
    name: str
    current_version: int


class ApplicantDeficiencyOut(CamelModel):
    id: str
    title: str
    description: str
    status: str  # open | responded | closed
    applicant_response: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    linked_items: list[ApplicantLinkedItemOut] = Field(default_factory=list)
    application_id: str = ""
    application_number: str = ""
    requested_by: str | None = None
    due_date: date | None = None
    requires_replacement: bool = False
    replacement_received: bool = False
    # action_required | awaiting_review | resolved — what the institution should understand.
    applicant_state: str = "action_required"
    affected_documents: list[ApplicantAffectedDocumentOut] = Field(default_factory=list)
    finding_refs: list[str] = Field(default_factory=list)
    responses: list[ApplicantResponseEntryOut] = Field(default_factory=list)


class ApplicantFindingDocumentOut(CamelModel):
    document_id: str | None = None
    name: str
    # Version the finding was recorded against, and the version currently on file.
    version: int | None = None
    current_version: int | None = None


class ApplicantFindingOut(CamelModel):
    """A finding the institution is allowed to see: officer-requested, or closed with an officer note.

    Internal automated diagnostics, scores, rule codes and forensic indicators are never included.
    """

    id: str
    reference: str
    kind: str  # officer_request | officer_update
    title: str
    explanation: str
    requested_correction: str | None = None
    document: ApplicantFindingDocumentOut
    page_reference: str | None = None
    snippet: str | None = None
    # open | response_needed | response_submitted | resolved | waived | accepted | rechecked
    status: str
    status_label: str
    next_action: str
    clarification_id: str | None = None
    officer_note: str | None = None
    updated_at: datetime | None = None
    # True when a newer document version has replaced the one this finding was recorded against.
    outdated_version: bool = False


class ApplicantEvidenceFieldOut(CamelModel):
    name: str
    value: str
    page_number: int | None = None
    # Present only when the extractor recorded real coordinates. Never estimated.
    bbox: dict | None = None


class ApplicantEvidenceOut(CamelModel):
    finding_id: str
    reference: str
    title: str
    explanation: str
    requested_correction: str | None = None
    document_id: str | None = None
    document_name: str
    version: int | None = None
    current_version: int | None = None
    mime_type: str = ""
    page_count: int | None = None
    page: int | None = None
    page_reference: str | None = None
    snippet: str | None = None
    fields: list[ApplicantEvidenceFieldOut] = Field(default_factory=list)
    clarification_id: str | None = None
    # Plain statement of how precise the location is, so the UI never implies more than is known.
    location_note: str = ""


class ApplicantLifecycleStepOut(CamelModel):
    key: str
    label: str
    state: str  # done | current | upcoming
    at: datetime | None = None
    detail: str | None = None


class ApplicantNextActionOut(CamelModel):
    kind: str  # respond_clarification | upload_documents | fix_document | submit_draft | continue_draft
    title: str
    reason: str
    application_id: str
    application_number: str
    clarification_id: str | None = None
    document_code: str | None = None


class ApplicantActivityOut(CamelModel):
    id: str
    source: str  # system | officer | you
    label: str
    detail: str | None = None
    application_id: str
    application_number: str
    timestamp: datetime


class ApplicantOverviewOut(CamelModel):
    """Counts have one definition each (see applicant_lifecycle) and match the dashboard cards."""

    active: int
    action_required: int
    under_scrutiny: int
    decision_recorded: int
    drafts: int
    next_actions: list[ApplicantNextActionOut] = Field(default_factory=list)
    recent_activity: list[ApplicantActivityOut] = Field(default_factory=list)


class ApplicantHistoryEntryOut(CamelModel):
    id: str
    timestamp: datetime
    label: str
    detail: str | None = None
    source: str = "system"  # you | officer | system


class ApplicantApplicationOut(CamelModel):
    id: str
    application_number: str
    institution_name: str
    category: str
    category_code: str
    program_name: str
    academic_year: str
    status: str
    status_label: str
    status_message: str
    submitted_at: datetime | None = None
    requirements: list[ApplicantRequirementOut] = Field(default_factory=list)
    deficiencies: list[ApplicantDeficiencyOut] = Field(default_factory=list)
    history: list[ApplicantHistoryEntryOut] = Field(default_factory=list)
    can_upload: bool = True
    can_resubmit: bool = False
    resubmit_blockers: list[str] = Field(default_factory=list)
    required_total: int = 0
    required_uploaded: int = 0
    officer_decision: str | None = None
    officer_decision_reason: str | None = None
    officer_decision_at: datetime | None = None
    corrections: list[dict] = Field(default_factory=list)
    # Closed issues the officer marked with a note (resolved / waived / accepted).
    officer_updates: list[dict] = Field(default_factory=list)
    stage: str = "draft"
    stage_label: str = ""
    lifecycle: list[ApplicantLifecycleStepOut] = Field(default_factory=list)
    findings: list[ApplicantFindingOut] = Field(default_factory=list)
    # Files uploaded earlier for a requirement the current category no longer lists. Kept, not deleted.
    other_documents: list[ApplicantDocumentOut] = Field(default_factory=list)
    updated_at: datetime | None = None
    contact_email: str | None = None
    # Category configuration this application is judged by (pinned) and the saved answers.
    info_fields: list[dict] = Field(default_factory=list)
    info_problems: dict[str, str] = Field(default_factory=dict)
    config_version: int | None = None
    config_available: bool = True


class ApplicantApplicationSummaryOut(CamelModel):
    stage: str = "draft"
    stage_label: str = ""
    updated_at: datetime | None = None
    category_code: str = ""
    next_action: ApplicantNextActionOut | None = None
    id: str
    application_number: str
    institution_name: str
    category: str
    program_name: str
    academic_year: str
    status: str
    status_label: str
    submitted_at: datetime | None = None
    open_clarifications: int = 0
    required_total: int = 0
    required_uploaded: int = 0
    officer_decision: str | None = None
    latest_request_title: str | None = None


class ApplicationDraftUpdateIn(BaseModel):
    """Partial update of a draft's details (autosave). Omitted fields are left unchanged."""

    category_code: str | None = None
    institution_name: str | None = Field(default=None, min_length=1, max_length=255)
    program_name: str | None = Field(default=None, max_length=255)
    academic_year: str | None = Field(default=None, max_length=32)
    info_values: dict[str, Any] | None = None
