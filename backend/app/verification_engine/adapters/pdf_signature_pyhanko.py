"""pyHanko PDF signature validation with configurable TRUST_STORE_DIR (D-17).

No CCA India certificates are bundled. Empty trust store → integrity checks only,
chain status chain_untrusted_no_trust_store, manual_review_required.
Scanned signatures/stamps → not_applicable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.models.enums import VerificationSource, VerificationStatus
from app.verification_engine.adapters.pdf_signature import verify_pdf_signature as verify_sigflags
from app.verification_engine.adapters.types import AdapterContext, AdapterResult

logger = logging.getLogger("praman.pyhanko")

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore


def _trust_roots() -> list[Path]:
    raw = (getattr(settings, "trust_store_dir", None) or "").strip()
    if not raw:
        return []
    root = Path(raw)
    if not root.is_dir():
        return []
    files: list[Path] = []
    for pattern in ("*.pem", "*.crt", "*.cer"):
        files.extend(root.glob(pattern))
    return files


def _looks_scanned_pdf(path: str) -> bool:
    """Heuristic: image-only pages without text → scanned stamps not cryptographically signed."""
    if fitz is None:
        return False
    try:
        doc = fitz.open(path)
        try:
            if doc.page_count == 0:
                return False
            text_chars = 0
            images = 0
            for page in doc:
                text_chars += len((page.get_text("text") or "").strip())
                images += len(page.get_images() or [])
            return text_chars < 40 and images > 0
        finally:
            doc.close()
    except Exception:  # noqa: BLE001
        return False


def _has_signature_indicators(path: str) -> tuple[bool, dict]:
    evidence: dict = {"engine": "pyhanko_or_sigflags"}
    if fitz is None:
        return False, evidence
    try:
        doc = fitz.open(path)
        try:
            sig_widgets = 0
            for page in doc:
                for w in page.widgets() or []:
                    if getattr(w, "field_type", None) == getattr(fitz, "PDF_WIDGET_TYPE_SIGNATURE", -1):
                        sig_widgets += 1
            sigflags = int(doc.get_sigflags() or 0)
            evidence.update({"signature_widgets": sig_widgets, "sigflags": sigflags})
            return bool(sig_widgets > 0 or (sigflags & 1)), evidence
        finally:
            doc.close()
    except Exception as exc:  # noqa: BLE001
        evidence["error"] = str(exc)
        return False, evidence


def _try_pyhanko_integrity(path: str) -> dict:
    """Best-effort integrity / modification-after-signing via pyHanko when installed."""
    out: dict = {"pyhanko_available": False, "modified_after_signing": None, "integrity_ok": None}
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader  # type: ignore
        from pyhanko.sign.validation import validate_pdf_signature  # type: ignore
    except ImportError:
        return out
    out["pyhanko_available"] = True
    try:
        with open(path, "rb") as fh:
            reader = PdfFileReader(fh)
            embedded = list(getattr(reader, "embedded_signatures", []) or [])
            if not embedded:
                out["integrity_ok"] = None
                return out
            # Validate first signature for integrity (no trust roots required for intactness)
            sig = embedded[0]
            status = validate_pdf_signature(sig)
            intact = getattr(status, "intact", None)
            valid = getattr(status, "valid", None)
            out["integrity_ok"] = bool(intact) if intact is not None else bool(valid)
            # modified_after_signing if not intact
            if intact is False:
                out["modified_after_signing"] = True
            elif intact is True:
                out["modified_after_signing"] = False
    except Exception as exc:  # noqa: BLE001
        logger.info("pyHanko validation limited: %s", exc)
        out["error"] = str(exc)[:200]
    return out


def verify_pdf_signature_pyhanko(ctx: AdapterContext) -> AdapterResult:
    now = datetime.now(timezone.utc)
    path = ctx.file_path
    if not path or not Path(path).exists():
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="File path unavailable for signature inspection.",
            checked_at=now,
            limitations=["Missing file on disk"],
            evidence={"signature_status": "signature_check_failed"},
        )

    if not (ctx.mime_type or "").lower().endswith("pdf") and not str(path).lower().endswith(".pdf"):
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="Digital signature check applies to PDF only.",
            checked_at=now,
            evidence={"signature_status": "not_applicable", "reason": "non_pdf"},
            limitations=["Non-PDF format"],
        )

    if _looks_scanned_pdf(path):
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="Scanned signature/stamp — cryptographic signature check not_applicable.",
            checked_at=now,
            evidence={
                "signature_status": "not_applicable",
                "reason": "scanned_signature_or_stamp",
                "engine": "pyhanko_adapter",
            },
            limitations=["Scanned wet-ink/stamp marks are not digital signatures."],
        )

    signed, evidence = _has_signature_indicators(path)
    roots = _trust_roots()
    evidence["trust_roots_loaded"] = len(roots)
    evidence["trust_store_dir"] = (settings.trust_store_dir or "") or None
    evidence["engine"] = "pyhanko_adapter"

    if not signed:
        # Fall back to sigflags path for richer unsigned messaging
        fallback = verify_sigflags(ctx)
        fallback.evidence = {**(fallback.evidence or {}), **evidence, "signature_status": "signature_absent"}
        fallback.limitations = list(fallback.limitations or []) + ["pyHanko adapter: no signature indicators"]
        return fallback

    integrity = _try_pyhanko_integrity(path)
    evidence.update(integrity)

    if integrity.get("modified_after_signing") is True:
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.MISMATCH_DETECTED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="PDF appears modified after signing (integrity check).",
            checked_at=now,
            evidence={**evidence, "signature_status": "signature_present_modified_after_signing"},
            limitations=["Integrity failure — not a full authenticity determination."],
        )

    if not roots:
        return AdapterResult(
            adapter="pdf_signature",
            claim_type="digital_signature",
            status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail=(
                "Signed PDF: integrity checked where possible, but no trust roots loaded "
                "(TRUST_STORE_DIR empty). Chain status: chain_untrusted_no_trust_store. "
                "Add official CCA India roots to TRUST_STORE_DIR — see docs/INTEGRATION_RESEARCH.md."
            ),
            checked_at=now,
            evidence={
                **evidence,
                "signature_status": "signature_present_chain_untrusted",
                "chain_status": "chain_untrusted_no_trust_store",
            },
            limitations=[
                "No CCA/trust anchors configured — chain cannot be validated.",
                "Do not treat as official verification.",
            ],
        )

    # Roots present — still honest: full chain validation requires correct CCA setup
    return AdapterResult(
        adapter="pdf_signature",
        claim_type="digital_signature",
        status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
        source=VerificationSource.LOCAL_VALIDATION,
        detail=(
            f"Signed PDF with {len(roots)} trust root(s) configured. "
            "Chain validation requires operator-supplied CCA roots; result remains manual_review_required "
            "unless a full pyHanko chain validation confirms trust."
        ),
        checked_at=now,
        evidence={
            **evidence,
            "signature_status": "signature_present_chain_untrusted",
            "chain_status": "chain_validation_incomplete",
        },
        limitations=["Trust-store present but automated CCA chain confirmation is limited in this build."],
    )
