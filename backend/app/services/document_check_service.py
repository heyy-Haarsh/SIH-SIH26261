"""Plain-language upload checks shown to applicants: document-type match and clarity.

These are *pre-checks derived from the persisted extraction run*. They describe whether the
file looks like the requested document and whether it could be read. They never claim the
document is authentic or compliant — that is for the scrutiny pipeline and the officer.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.document_processing.ocr_processor import tesseract_status
from app.models.enums import ExtractionRunStatus, SemanticDocumentCategory
from app.schemas.common import DocumentCheckOut

CATEGORY_LABELS: dict[str, str] = {
    SemanticDocumentCategory.AFFIDAVIT.value: "affidavit",
    SemanticDocumentCategory.AFFIDAVIT_2.value: "affidavit",
    SemanticDocumentCategory.LAND_OR_LEASE.value: "land ownership / lease deed",
    SemanticDocumentCategory.AFFILIATION.value: "university affiliation letter",
    SemanticDocumentCategory.BUILDING.value: "building plan / occupancy document",
    SemanticDocumentCategory.FIRE_NOC.value: "fire safety certificate / NOC",
    SemanticDocumentCategory.TRUST_OR_SOCIETY.value: "trust / society document",
    SemanticDocumentCategory.AICTE_PAYMENT_RECEIPT.value: "payment receipt",
    SemanticDocumentCategory.AUDITED_ACCOUNTS.value: "audited accounts",
    SemanticDocumentCategory.STRUCTURAL_STABILITY.value: "structural stability certificate",
    SemanticDocumentCategory.SATELLITE_MAP.value: "satellite / geotagged map",
}

_LOW_OCR_CONFIDENCE = 0.6
_SCAN_KINDS = {"scanned_pdf", "mixed_pdf", "image"}


def _val(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def detected_label(category: str | None) -> str | None:
    if not category or category in (
        SemanticDocumentCategory.UNKNOWN.value,
        SemanticDocumentCategory.OTHER.value,
    ):
        return None
    return CATEGORY_LABELS.get(category, category.replace("_", " ").lower())


def _language_note(run, *, ocr_involved: bool) -> str | None:
    """Honest Marathi/Hindi OCR statement; only shown when OCR was (or needed to be) used."""
    if not ocr_involved:
        return None
    status = tesseract_status()
    if not status.get("available"):
        return (
            "Text recognition (OCR) is not available on this server, so scanned pages "
            "— including Marathi or Hindi — cannot be read. Upload a text-based PDF instead."
        )
    usable = set(status.get("languages_usable") or [])
    missing = [l for l in ("mar", "hin") if l in get_settings().ocr_language_list and l not in usable]
    if "mar" in missing:
        return (
            "Marathi text recognition is configured but its language data is not installed "
            "on this server, so Marathi scans may not be read correctly. The officer will "
            "review the original file."
        )
    if "mar" in usable:
        return (
            "Marathi text recognition is enabled. Automatic field extraction works best on "
            "English text and numbers; the officer reviews anything it cannot read."
        )
    return None


def build_document_check(*, requirement_name: str, run, file_checks: dict | None = None) -> DocumentCheckOut:
    """Build the applicant-facing check from the latest ExtractionRun (may be None)."""
    if run is None:
        return DocumentCheckOut(
            type_match="not_checked",
            type_match_message="Document type has not been checked yet.",
            expected_type=requirement_name,
            clarity="not_checked",
            clarity_message="Readability has not been checked yet.",
            needs_attention=False,
        )

    status = _val(run.status)
    predicted = _val(run.predicted_category)
    detected = detected_label(predicted)
    content_kind = _val(run.content_kind)
    scan_like = content_kind in _SCAN_KINDS or (run.pages_ocr or 0) > 0
    ocr_needed = scan_like or status in (
        ExtractionRunStatus.OCR_UNAVAILABLE.value,
        ExtractionRunStatus.REQUIRES_OCR.value,
    )

    # ---- clarity ---------------------------------------------------------------------
    clarity = "clear"
    clarity_message = "The file is readable."
    if status in (ExtractionRunStatus.FAILED.value, ExtractionRunStatus.UNSUPPORTED.value):
        clarity = "unreadable"
        clarity_message = (
            "We could not read this file. Upload a clear PDF, JPG or PNG that opens normally."
        )
    elif status in (
        ExtractionRunStatus.OCR_UNAVAILABLE.value,
        ExtractionRunStatus.REQUIRES_OCR.value,
    ):
        clarity = "unclear"
        clarity_message = (
            "This looks like a scan or photo, and its text could not be read automatically. "
            "A text-based PDF reads best; otherwise the officer will review the original."
        )
    elif status == ExtractionRunStatus.REQUIRES_MANUAL_REVIEW.value or (
        (run.pages_with_text or 0) == 0 and (run.pages_ocr or 0) == 0
    ):
        clarity = "unreadable"
        clarity_message = (
            "No readable text was found. If this is a photo or scan, upload a sharper, "
            "well-lit copy with all four corners visible."
        )
    else:
        confidences = [
            f.ocr_confidence
            for f in (getattr(run, "fields", None) or [])
            if f.ocr_confidence is not None
        ]
        if confidences and (sum(confidences) / len(confidences)) < _LOW_OCR_CONFIDENCE:
            clarity = "unclear"
            clarity_message = (
                "The scan is hard to read (low text-recognition confidence). "
                "Upload a sharper copy if you can."
            )
        elif (file_checks or {}).get("warnings"):
            clarity_message = "The file is readable. Minor file advisories were noted."

    # ---- type match ------------------------------------------------------------------
    if status in (ExtractionRunStatus.FAILED.value, ExtractionRunStatus.UNSUPPORTED.value):
        type_match = "not_checked"
        type_msg = "Document type could not be checked because the file could not be read."
    elif detected is None:
        type_match = "unclear"
        type_msg = (
            f"We could not tell from the content whether this is a {requirement_name}. "
            "Please confirm it is the right file."
        )
    elif run.category_mismatch:
        type_match = "mismatch"
        type_msg = (
            f"This looks like a {detected}, but it was uploaded as “{requirement_name}”. "
            "If it is the wrong file, upload the correct one."
        )
    else:
        type_match = "matched"
        type_msg = f"This looks like the requested document ({requirement_name})."

    return DocumentCheckOut(
        type_match=type_match,
        type_match_message=type_msg,
        expected_type=requirement_name,
        detected_type=detected,
        clarity=clarity,
        clarity_message=clarity_message,
        language_note=_language_note(run, ocr_involved=ocr_needed),
        needs_attention=type_match == "mismatch" or clarity in ("unclear", "unreadable"),
    )
