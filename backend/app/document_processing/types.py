"""Plain data containers passed between pipeline modules (no ORM, no I/O)."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Optional

from app.models.enums import FindingSeverity, ReconciliationOutcome, ValidationOutcome


class ModuleStatus(str, Enum):
    AVAILABLE = "available"
    LIMITED = "limited"  # works, but with reduced capability (e.g. filename heuristics only)
    UNAVAILABLE = "unavailable"  # not implemented / not configured in this deployment
    FAILED = "failed"


@dataclass
class ModuleResult:
    """Truthful capability / outcome report for a pipeline module."""

    module: str
    status: ModuleStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


# ---- Module 1: intake ------------------------------------------------------
@dataclass
class FileCheck:
    name: str
    passed: bool
    detail: str
    blocking: bool = False  # a failed blocking check rejects the upload


@dataclass
class FileWarning:
    code: str
    message: str


@dataclass
class IntakeResult:
    accepted: bool
    file_name: str
    extension: str
    size_bytes: int
    sha256: str
    declared_content_type: Optional[str]
    detected_type: str  # pdf | png | jpeg | docx | text | unknown
    mime_type: str  # canonical mime for the detected/accepted type
    checks: list[FileCheck] = field(default_factory=list)
    warnings: list[FileWarning] = field(default_factory=list)
    page_count: Optional[int] = None
    rejection_status: int = 400
    rejection_code: str = ""
    rejection_reason: str = ""


# ---- Module 2: classification ---------------------------------------------
@dataclass
class ClassificationResult:
    status: ModuleStatus
    label: Optional[str] = None  # a requirement code, or None when unknown
    confidence: Optional[float] = None  # None: heuristic match, no calibrated confidence
    method: str = "none"
    rationale: str = ""


# ---- Module 3/4: extraction + normalization -------------------------------
@dataclass
class ExtractedFieldDraft:
    field_name: str  # canonical snake_case key, e.g. "institution_name"
    value: str
    confidence: Optional[float] = None
    page_reference: Optional[str] = None
    method: str = "text_key_value"


# ---- Module 5: reconciliation ---------------------------------------------
@dataclass
class FieldRecord:
    field_name: str
    value: str
    document_id: str
    document_name: str
    page_reference: Optional[str] = None
    page_number: Optional[int] = None
    extracted_field_id: Optional[str] = None
    evidence_snippet: Optional[str] = None


@dataclass
class DiscrepancyValue:
    document_id: str
    document_name: str
    value: str
    page: Optional[str] = None
    page_number: Optional[int] = None
    extracted_field_id: Optional[str] = None
    normalized_value: Optional[str] = None
    evidence_snippet: Optional[str] = None


@dataclass
class DiscrepancyDraft:
    field_name: str
    values: list[DiscrepancyValue]
    outcome: ReconciliationOutcome = ReconciliationOutcome.MISMATCH
    severity: FindingSeverity = FindingSeverity.MANUAL_REVIEW
    validation_outcome: ValidationOutcome = ValidationOutcome.MANUAL_REVIEW
    title: str = ""
    description: str = ""
    match_kind: Optional[str] = None  # exact | normalization
    fingerprint: Optional[str] = None


# ---- Module 6/9: rule evaluation + aggregation ----------------------------
@dataclass
class EvidenceDraft:
    description: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    page_reference: Optional[str] = None
    extracted_field_id: Optional[str] = None


@dataclass
class FindingDraft:
    title: str
    description: str
    severity: FindingSeverity
    outcome: ValidationOutcome
    rule_code: str
    rule_name: str
    rule_version: str
    handbook_ref: str = ""
    document_id: Optional[str] = None
    evidence: list[EvidenceDraft] = field(default_factory=list)


@dataclass
class EvalDocument:
    """A document (latest version) as seen by the rule engine."""

    document_id: str
    requirement_code: str
    requirement_name: str
    file_name: str
    extension: str
    mime_type: str
    declared_content_type: Optional[str]
    size_bytes: int
    sha256: str
    warnings: list[FileWarning] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    classification: Optional[ClassificationResult] = None


@dataclass
class EvalContext:
    category_code: str
    program_name: str
    academic_year: str
    requirements: list[dict[str, Any]]
    documents: list[EvalDocument]
    discrepancies: list[DiscrepancyDraft]
    module_results: list[ModuleResult]
    today: date


@dataclass
class AggregationResult:
    findings: list[FindingDraft]
    summary: dict[str, Any]
    overall_outcome: ValidationOutcome
