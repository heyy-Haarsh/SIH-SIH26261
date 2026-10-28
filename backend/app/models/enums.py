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
    REGIONAL_OFFICER = "regional_officer"


class ApplicationStatus(StrEnum):
    """Scrutiny workflow statuses.

    Phase 5 primary: submitted → processing → under_scrutiny →
    clarification_required ↔ resubmitted → recommended | rejected.
    Legacy values remain readable for older seed/demo rows.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    UNDER_SCRUTINY = "under_scrutiny"
    CLARIFICATION_REQUIRED = "clarification_required"
    RESUBMITTED = "resubmitted"
    RECOMMENDED = "recommended"
    REJECTED = "rejected"
    # Legacy (still valid in DB / UI)
    AWAITING_REVIEW = "awaiting_review"
    UNDER_REVIEW = "under_review"
    DEFICIENCY = "deficiency"
    MANUAL_REVIEW = "manual_review"
    APPROVED = "approved"


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
    CLARIFICATION = "clarification"
    RECOMMEND = "recommend"
    APPROVE = "approve"  # legacy alias of recommend
    REJECT = "reject"
    RESUBMIT = "resubmit"


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
    AFFIDAVIT_2 = "affidavit_2"
    AFFILIATION = "affiliation"
    AICTE_PAYMENT_RECEIPT = "aicte_payment_receipt"
    AUDITED_ACCOUNTS = "audited_accounts"
    STRUCTURAL_STABILITY = "structural_stability"
    SATELLITE_MAP = "satellite_map"
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


class ForensicsRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ForensicsIndicatorStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WAIVED = "waived"
    ACCEPTED = "accepted"
    CLEARED = "cleared"


class ForensicsRiskClass(StrEnum):
    """Distinguishes technical anomalies from authenticity concerns — never 'fraud'."""

    INFORMATIONAL = "informational"
    CHECK_LIMITATION = "check_limitation"  # missing metadata/signature/unavailable check
    TECHNICAL_ANOMALY = "technical_anomaly"
    AUTHENTICITY_CONCERN = "authenticity_concern"  # stronger signal; still not fraud
    POSSIBLE_DUPLICATE = "possible_duplicate"


class ForensicsIndicatorCode(StrEnum):
    METADATA_ANOMALY = "metadata_anomaly"
    MALFORMED_STRUCTURE = "malformed_structure"
    UNUSUAL_MODIFICATION = "unusual_modification"
    ENCRYPTION_DETECTED = "encryption_detected"
    CORRUPT_UNREADABLE = "corrupt_unreadable"
    UNSUPPORTED_FORMAT = "unsupported_format"
    SIGNATURE_ABSENT = "signature_absent"
    SIGNATURE_PRESENT = "signature_present"
    SIGNATURE_INVALID = "signature_invalid"
    QR_CHECK_UNAVAILABLE = "qr_check_unavailable"
    QR_NOT_FOUND = "qr_not_found"
    QR_DETECTED_UNVERIFIED = "qr_detected_unverified"
    DUPLICATE_HASH = "duplicate_hash"
    NEAR_DUPLICATE = "near_duplicate"
    EXTERNAL_CLAIM_SIMULATED = "external_claim_simulated"
    EXTERNAL_CLAIM_UNAVAILABLE = "external_claim_unavailable"
    CLEAN_SCAN = "clean_scan"


# ---- Phase 7: per-document three-layer statuses -------------------------------


class RuleValidationStatus(StrEnum):
    """Layer 1 — extraction/rules. Passing never proves authenticity."""

    PENDING = "pending"
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    MANUAL_REVIEW = "manual_review"
    SKIPPED = "skipped"
    ERROR = "error"
    UNREADABLE = "unreadable"


class ExternalVerificationLayerStatus(StrEnum):
    """Layer 2 — external/local verification adapters (independent of Layer 1)."""

    PENDING = "pending"
    VERIFIED_BY_SOURCE = "verified_by_source"
    MISMATCH_DETECTED = "mismatch_detected"
    SOURCE_UNAVAILABLE = "source_unavailable"
    MANUAL_VERIFICATION_REQUIRED = "manual_verification_required"
    SIMULATED_RESULT = "simulated_result"
    NOT_APPLICABLE = "not_applicable"
    PARTIAL = "partial"
    ERROR = "error"


class DocumentReviewStatus(StrEnum):
    """Layer 3 — human review. Independent of automated layers."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    WAIVED = "waived"
    ACCEPTED = "accepted"
    NOT_REQUIRED = "not_required"


class DocumentVerificationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_PARTIAL = "completed_partial"
    FAILED = "failed"


class VerificationCheckLayer(StrEnum):
    RULES = "layer1_rules"
    EXTERNAL = "layer2_external"
    REVIEW = "layer3_review"
