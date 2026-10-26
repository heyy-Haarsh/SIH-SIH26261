"""Enumerations shared by models, schemas and services.

String values intentionally match the frontend TypeScript union types.
"""

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class UserRole(StrEnum):
    APPLICANT = "applicant"
    OFFICER = "officer"
    ADMIN = "admin"


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    AWAITING_REVIEW = "awaiting_review"
    UNDER_REVIEW = "under_review"
    DEFICIENCY = "deficiency"
    MANUAL_REVIEW = "manual_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESUBMITTED = "resubmitted"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class FindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WAIVED = "waived"
    ACCEPTED = "accepted"


class ValidationOutcome(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAILED = "failed"
    PENDING = "pending"
    MANUAL_REVIEW = "manual_review"
    VERIFICATION_UNAVAILABLE = "verification_unavailable"


class VerificationSource(StrEnum):
    AUTHORIZED_LIVE = "authorized_live"
    LOCAL_VALIDATION = "local_validation"
    SIMULATED_DEV = "simulated_dev"
    MANUAL_REVIEWER = "manual_reviewer"


class VerificationStatus(StrEnum):
    VERIFIED_BY_SOURCE = "verified_by_source"
    MISMATCH_DETECTED = "mismatch_detected"
    EXPIRED = "expired"
    VERIFICATION_PENDING = "verification_pending"
    SOURCE_UNAVAILABLE = "source_unavailable"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    SIMULATED_RESULT = "simulated_result"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    REPLACED = "replaced"
    REJECTED = "rejected"


class ValidationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DeficiencyStatus(StrEnum):
    OPEN = "open"
    RESPONDED = "responded"
    CLOSED = "closed"


class ReviewDecisionType(StrEnum):
    NOTE = "note"
    DEFICIENCY = "deficiency"
    MANUAL_REVIEW = "manual_review"
    APPROVE = "approve"
    REJECT = "reject"


class ExtractionMethod(StrEnum):
    FILENAME_METADATA = "filename_metadata"
    TEXT_KEY_VALUE = "text_key_value"
    PDF_TEXT = "pdf_text"
    OCR = "ocr"
    REGEX = "regex"
    MANUAL = "manual"
    AI_MODEL = "ai_model"  # reserved — ENABLE_AI_EXTRACTION only; not required for local extraction


class ExtractionRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    REQUIRES_OCR = "requires_ocr"
    OCR_UNAVAILABLE = "ocr_unavailable"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"


class DocumentContentKind(StrEnum):
    DIGITAL_PDF = "digital_pdf"
    SCANNED_PDF = "scanned_pdf"
    MIXED_PDF = "mixed_pdf"
    IMAGE = "image"
    TEXT = "text"
    DOCX = "docx"
    UNSUPPORTED = "unsupported"
    UNREADABLE = "unreadable"


class SemanticDocumentCategory(StrEnum):
    LAND_OR_LEASE = "land_or_lease"
    FIRE_NOC = "fire_noc"
    BUILDING = "building"
    TRUST_OR_SOCIETY = "trust_or_society"
    AFFIDAVIT = "affidavit"
    AFFILIATION = "affiliation"
    OTHER = "other"
    UNKNOWN = "unknown"


class FieldReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    CONFLICT = "conflict"


class ReconciliationOutcome(StrEnum):
    """Explainable cross-document comparison outcomes — never 'fraud'."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING_DATA = "MISSING_DATA"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ReconciliationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationItemStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WAIVED = "waived"
    ACCEPTED = "accepted"
    CLEARED = "cleared"  # no longer present after a later rerun
