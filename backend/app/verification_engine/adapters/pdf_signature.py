"""Local PDF digital-signature presence / flag validation (PyMuPDF).

Does not perform full PKI certificate-chain validation against a trust store.
Presence ≠ cryptographic authenticity confirmation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.models.enums import VerificationSource, VerificationStatus
from app.verification_engine.adapters.types import AdapterContext, AdapterResult

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore


def verify_pdf_signature(ctx: AdapterContext) -> AdapterResult:
    now = datetime.now(timezone.utc)
    if not ctx.file_path or not Path(ctx.file_path).exists():
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="File path unavailable for signature inspection.",
            checked_at=now,
            limitations=["Missing file on disk"],
        )
    if not (ctx.mime_type or "").lower().endswith("pdf") and not str(ctx.file_path).lower().endswith(
        ".pdf"
    ):
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="Digital signature check applies to PDF only; non-PDF marked for manual review.",
            checked_at=now,
            evidence={"mime": ctx.mime_type},
            limitations=["Non-PDF format"],
        )
    if fitz is None:
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="PyMuPDF not installed; signature check unavailable.",
            checked_at=now,
            limitations=["PyMuPDF missing"],
        )
    try:
        doc = fitz.open(ctx.file_path)
        try:
            sig_widgets = 0
            for page in doc:
                for w in page.widgets() or []:
                    if getattr(w, "field_type", None) == getattr(fitz, "PDF_WIDGET_TYPE_SIGNATURE", -1):
                        sig_widgets += 1
            sigflags = int(doc.get_sigflags() or 0)
        finally:
            doc.close()
    except Exception as exc:  # noqa: BLE001
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.LOCAL_VALIDATION,
            detail=f"PDF signature inspection failed: {exc}",
            checked_at=now,
            limitations=["Inspection error"],
        )

    evidence = {"signature_widgets": sig_widgets, "sigflags": sigflags}
    # Bit 2 in Adobe sigflags indicates problems with signatures
    if sigflags & 2:
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.MISMATCH_DETECTED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="PDF signature flags indicate an invalid or problematic signature (local heuristic).",
            checked_at=now,
            evidence=evidence,
            limitations=[
                "Local sigflags heuristic only — not a full certificate-chain validation.",
                "Does not prove or disprove authenticity by itself.",
            ],
        )
    if sig_widgets > 0 or (sigflags & 1):
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="Signature field/flags present; cryptographic chain not verified in this build.",
            checked_at=now,
            evidence=evidence,
            limitations=[
                "Presence of signature widgets ≠ verified authenticity.",
                "Full PKI validation against a trust store is not implemented.",
            ],
        )
    return AdapterResult(
        adapter="pdf_signature",
        claim_type="digital_signature",
        status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
        source=VerificationSource.LOCAL_VALIDATION,
        detail="No PDF digital signature detected (check limitation — not automatic tampering).",
        checked_at=now,
        evidence=evidence,
        limitations=["Unsigned PDF is a check limitation, not proof of fraud."],
    )
