"""Scrutiny-officer review DTOs: grouped issues, document cards and per-document pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import CamelModel, DocumentCheckOut, ExtractedFieldOut


class HandbookReferenceOut(CamelModel):
    """Verified AICTE Handbook citation, or an explicit 'unverified' marker. Never invented."""

    status: str  # verified | unverified
    edition: str | None = None
    section: str | None = None
    page: str | None = None
    title: str | None = None
    note: str = ""


class IssueEvidenceOut(CamelModel):
    text: str
    document_id: str | None = None
    document_name: str | None = None
    page_reference: str | None = None


class RelatedDocumentOut(CamelModel):
    id: str
    name: str


class ScrutinyIssueOut(CamelModel):
    key: str
    title: str
    explanation: str
    severity: str  # failed | manual_review | warning | info
    status: str  # open | resolved | waived | accepted | superseded (coarse: open == still active)
    # Fine-grained lifecycle: open | under_review | clarification_requested | reopened | resolved | …
    lifecycle_status: str = "open"
    source: str  # rule | document_rule | external | reconciliation | forensics | classification | file
    layer: str  # intake | classification | layer1 | layer2 | cross_document | layer3
    document_id: str | None = None
    document_name: str | None = None
    requirement_code: str | None = None
    related_documents: list[RelatedDocumentOut] = Field(default_factory=list)
    applicant_action: str | None = None
    handbook: HandbookReferenceOut
    finding_ids: list[str] = Field(default_factory=list)
    check_ids: list[str] = Field(default_factory=list)
    occurrences: int = 1
    evidence: list[IssueEvidenceOut] = Field(default_factory=list)


class DocumentIssueGroupOut(CamelModel):
    document_id: str | None = None
    document_name: str
    requirement_code: str | None = None
    scope: str  # document | cross_document | application
    issues: list[ScrutinyIssueOut] = Field(default_factory=list)
    open_count: int = 0
    highest_severity: str | None = None


class DocumentCardOut(CamelModel):
    id: str
    name: str
    requirement_code: str
    file_name: str
    version: int
    mime_type: str
    size_bytes: int
    uploaded_at: datetime
    page_count: int | None = None
    rule_validation_status: str | None = None
    external_verification_status: str | None = None
    review_status: str | None = None
    document_check: DocumentCheckOut | None = None
    open_issue_count: int = 0
    highest_severity: str | None = None
    can_preview: bool = True


class MissingDocumentOut(CamelModel):
    code: str
    name: str
    mandatory: bool


class DeficiencyContextOut(CamelModel):
    id: str
    title: str
    description: str
    status: str
    applicant_response: str | None = None
    created_at: datetime
    responded_at: datetime | None = None


class DecisionContextOut(CamelModel):
    """Why the application is in clarification / rejected, and what the applicant must correct."""

    status: str
    clarification_requests: list[DeficiencyContextOut] = Field(default_factory=list)
    final_decision: str | None = None
    final_decision_reason: str | None = None
    final_decision_by: str | None = None
    final_decision_at: str | None = None
    must_correct: list[str] = Field(default_factory=list)
    must_correct_rows: list[dict] = Field(default_factory=list)
    clarification_draft_title: str = ""
    clarification_draft_body: str = ""
    rejection_draft_body: str = ""


class ScrutinyReviewOut(CamelModel):
    application_id: str
    application_number: str
    institution_name: str
    status: str
    generated_at: datetime
    validation_run_id: str | None = None
    validation_completed_at: datetime | None = None
    documents: list[DocumentCardOut] = Field(default_factory=list)
    missing_documents: list[MissingDocumentOut] = Field(default_factory=list)
    issue_groups: list[DocumentIssueGroupOut] = Field(default_factory=list)
    open_issue_count: int = 0
    resolved_issue_count: int = 0
    historical_finding_count: int = 0
    limitations: list[str] = Field(default_factory=list)
    decision: DecisionContextOut
    disclaimer: str


class PipelineDetailOut(CamelModel):
    label: str
    value: str


class PipelineCheckOut(CamelModel):
    id: str
    title: str
    outcome: str
    severity: str = "info"
    status: str = "open"  # open | resolved | waived | accepted | passed
    detail: str = ""
    source: str | None = None
    mode: str | None = None  # real | simulated | unavailable | local
    limitations: list[str] = Field(default_factory=list)
    resolution_reason: str | None = None
    resolvable: bool = False
    resolve_kind: str | None = None  # finding | check | reconciliation | forensics
    handbook: HandbookReferenceOut | None = None


class PipelineStageOut(CamelModel):
    key: str  # intake | classification | layer1 | layer2 | layer3
    title: str
    status: str  # pass | warning | failed | manual_review | unavailable | not_run
    summary: str
    details: list[PipelineDetailOut] = Field(default_factory=list)
    checks: list[PipelineCheckOut] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DocumentVersionBriefOut(CamelModel):
    version: int
    file_name: str
    uploaded_at: datetime
    size_bytes: int
    sha256: str
    is_current: bool


class DocumentReportOut(CamelModel):
    document: DocumentCardOut
    stages: list[PipelineStageOut] = Field(default_factory=list)
    issues: list[ScrutinyIssueOut] = Field(default_factory=list)
    extracted_fields: list[ExtractedFieldOut] = Field(default_factory=list)
    versions: list[DocumentVersionBriefOut] = Field(default_factory=list)
    disclaimer: str


class HandbookReferenceIn(BaseModel):
    reference_key: str
    edition: str = ""
    section: str = ""
    page: str = ""
    title: str = ""
    source_note: str = ""
    academic_year: str = ""
    applicable_categories: str = ""
    verified: bool = False

    @field_validator("reference_key")
    @classmethod
    def _key(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 128:
            raise ValueError("reference_key is required (max 128 characters).")
        return v


class HandbookReferenceAdminOut(CamelModel):
    id: str
    reference_key: str
    edition: str
    section: str
    page: str
    title: str
    source_note: str
    academic_year: str = ""
    applicable_categories: str = ""
    verified: bool
    verified_by: str | None = None
    verified_at: datetime | None = None
    updated_at: datetime | None = None
