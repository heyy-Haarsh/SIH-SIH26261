"""Module 8: local authenticity / tamper-risk analysis.

Produces explainable indicators only. Missing metadata or an absent digital
signature is a check limitation — never automatic proof of tampering or fraud.
External authority claims are labeled simulated or source_unavailable.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.document_processing.interfaces import ForensicsModule
from app.document_processing.types import ModuleResult, ModuleStatus
from app.models.enums import (
    FindingSeverity,
    ForensicsIndicatorCode,
    ForensicsRiskClass,
    VerificationStatus,
)

ENGINE_VERSION = "forensics-0.1"

_PDF_HEADER = re.compile(br"%PDF-(\d\.\d)")
_DATE_RE = re.compile(
    r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?"
)


@dataclass
class ForensicsEvidenceDraft:
    description: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    page_number: Optional[int] = None
    page_reference: Optional[str] = None
    detail: Optional[str] = None


@dataclass
class ForensicsIndicatorDraft:
    code: ForensicsIndicatorCode
    risk_class: ForensicsRiskClass
    severity: FindingSeverity
    title: str
    description: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    affected_pages: list[int] = field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.VERIFICATION_PENDING
    evidence: list[ForensicsEvidenceDraft] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""


@dataclass
class DocForensicsInput:
    document_id: str
    document_name: str
    extension: str
    mime_type: str
    sha256: str
    storage_path: str
    content: Optional[bytes] = None


@dataclass
class ForensicsCompareResult:
    indicators: list[ForensicsIndicatorDraft] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    input_fingerprint: str = ""
    module_result: Optional[ModuleResult] = None


def _fp(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:40]


def _parse_pdf_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    m = _DATE_RE.search(raw)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        ss = int(m.group(6) or 0)
        return datetime(y, mo, d, hh, mm, ss)
    except ValueError:
        return None


def _dhash_hex(image, hash_size: int = 8) -> Optional[str]:
    """Difference hash for near-duplicate detection (Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    if not isinstance(image, Image.Image):
        return None
    img = image.convert("L").resize((hash_size + 1, hash_size))
    pixels = list(img.getdata())
    bits = []
    for row in range(hash_size):
        row_start = row * (hash_size + 1)
        for col in range(hash_size):
            left = pixels[row_start + col]
            right = pixels[row_start + col + 1]
            bits.append("1" if left > right else "0")
    # pack to hex
    value = int("".join(bits), 2)
    return f"{value:0{hash_size * hash_size // 4}x}"


def _hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return 64
    return sum(c1 != c2 for c1, c2 in zip(a, b))


class LocalForensicsModule(ForensicsModule):
    """Local PDF/image forensics with honest capability reporting."""

    name = "forensics"

    def capability(self) -> ModuleResult:
        limitations = []
        try:
            import fitz  # noqa: F401
            pdf_ok = True
        except ImportError:
            pdf_ok = False
            limitations.append("PyMuPDF unavailable — PDF structure/metadata analysis disabled")
        try:
            from PIL import Image  # noqa: F401
            pil_ok = True
        except ImportError:
            pil_ok = False
            limitations.append("Pillow unavailable — perceptual near-duplicate checks disabled")
        qr_ok = False
        try:
            import pyzbar  # noqa: F401

            qr_ok = True
        except ImportError:
            limitations.append(
                "QR decode library not installed — QR presence may be noted but claims are not verified"
            )

        if not pdf_ok and not pil_ok:
            return ModuleResult(
                module=self.name,
                status=ModuleStatus.UNAVAILABLE,
                message="Local forensics libraries are not available in this deployment.",
                data={"limitations": limitations},
            )
        status = ModuleStatus.AVAILABLE if pdf_ok else ModuleStatus.LIMITED
        return ModuleResult(
            module=self.name,
            status=status,
            message=(
                "Local PDF metadata/structure/signature heuristics and hash/near-duplicate checks. "
                "Never labels fraud. Missing metadata or unsigned PDFs are limitations, not tampering."
            ),
            data={
                "engine": ENGINE_VERSION,
                "pdf": pdf_ok,
                "perceptualHash": pil_ok,
                "qrDecode": qr_ok,
                "limitations": limitations,
            },
        )

    def analyze(self, *, file_name: str, content: Optional[bytes] = None) -> ModuleResult:
        """Single-file analyze (pipeline compatibility). Prefer ``compare_documents``."""
        cap = self.capability()
        if content is None:
            return ModuleResult(
                module=self.name,
                status=ModuleStatus.LIMITED,
                message="No file bytes provided — forensics skipped for this call.",
                data=cap.data,
            )
        doc = DocForensicsInput(
            document_id="adhoc",
            document_name=file_name,
            extension=Path(file_name).suffix.lstrip(".").lower(),
            mime_type="",
            sha256=hashlib.sha256(content).hexdigest(),
            storage_path="",
            content=content,
        )
        result = self.compare_documents([doc])
        return ModuleResult(
            module=self.name,
            status=cap.status,
            message=f"{len(result.indicators)} indicator(s) from ad-hoc analyze.",
            data={"indicators": len(result.indicators), "limitations": result.limitations},
        )

    def compare_documents(self, docs: list[DocForensicsInput]) -> ForensicsCompareResult:
        cap = self.capability()
        limitations = list((cap.data or {}).get("limitations") or [])
        indicators: list[ForensicsIndicatorDraft] = []
        perceptual: list[tuple[DocForensicsInput, str]] = []

        for doc in docs:
            content = doc.content
            if content is None and doc.storage_path:
                try:
                    content = Path(doc.storage_path).read_bytes()
                except OSError:
                    indicators.append(
                        self._indicator(
                            code=ForensicsIndicatorCode.CORRUPT_UNREADABLE,
                            risk=ForensicsRiskClass.CHECK_LIMITATION,
                            severity=FindingSeverity.WARNING,
                            title="Document bytes unavailable",
                            description=(
                                f"Could not read stored file for '{doc.document_name}'. "
                                "This is a processing limitation, not a fraud determination."
                            ),
                            doc=doc,
                            verification=VerificationStatus.SOURCE_UNAVAILABLE,
                            evidence=[
                                ForensicsEvidenceDraft(
                                    description=f"storage_path unreadable: {doc.storage_path}",
                                    document_id=doc.document_id,
                                    document_name=doc.document_name,
                                )
                            ],
                        )
                    )
                    continue

            if content is None:
                continue

            ext = (doc.extension or Path(doc.document_name).suffix.lstrip(".")).lower()
            if ext == "pdf" or content[:5] == b"%PDF-":
                indicators.extend(self._analyze_pdf(doc, content))
                ph = self._pdf_page_dhash(content)
                if ph:
                    perceptual.append((doc, ph))
            elif ext in {"png", "jpg", "jpeg"} or content[:3] == b"\xff\xd8\xff" or content[:8] == b"\x89PNG\r\n\x1a\n":
                indicators.extend(self._analyze_image(doc, content))
                try:
                    from PIL import Image

                    img = Image.open(io.BytesIO(content))
                    ph = _dhash_hex(img)
                    if ph:
                        perceptual.append((doc, ph))
                except Exception:
                    pass
            elif ext in {"txt"}:
                # Text uploads: only informational clean scan — no PDF forensics
                indicators.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.UNSUPPORTED_FORMAT,
                        risk=ForensicsRiskClass.INFORMATIONAL,
                        severity=FindingSeverity.INFO,
                        title="Forensics limited for text upload",
                        description=(
                            f"'{doc.document_name}' is plain text. PDF metadata/signature/QR "
                            "checks do not apply. Absence of PDF signals is not tampering."
                        ),
                        doc=doc,
                        verification=VerificationStatus.VERIFIED_BY_SOURCE,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description="format=text/plain; PDF forensics skipped",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                    )
                )
            else:
                indicators.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.UNSUPPORTED_FORMAT,
                        risk=ForensicsRiskClass.CHECK_LIMITATION,
                        severity=FindingSeverity.INFO,
                        title="Unsupported format for deep forensics",
                        description=(
                            f"Deep authenticity analysis is not implemented for "
                            f"'{doc.document_name}' ({ext or 'unknown'}). "
                            "Not treated as a tamper finding."
                        ),
                        doc=doc,
                        verification=VerificationStatus.SOURCE_UNAVAILABLE,
                    )
                )

        # Exact duplicate hashes across documents
        by_hash: dict[str, list[DocForensicsInput]] = {}
        for d in docs:
            if d.sha256:
                by_hash.setdefault(d.sha256, []).append(d)
        for sha, group in by_hash.items():
            if len(group) < 2:
                continue
            indicators.append(
                self._indicator(
                    code=ForensicsIndicatorCode.DUPLICATE_HASH,
                    risk=ForensicsRiskClass.POSSIBLE_DUPLICATE,
                    severity=FindingSeverity.WARNING,
                    title="Identical file checksum across documents",
                    description=(
                        f"{len(group)} documents share SHA-256 {sha[:16]}…. "
                        "Possible re-upload or shared file — not a fraud determination."
                    ),
                    doc=group[0],
                    verification=VerificationStatus.VERIFIED_BY_SOURCE,
                    evidence=[
                        ForensicsEvidenceDraft(
                            description=f"{g.document_name} sha256={sha[:16]}…",
                            document_id=g.document_id,
                            document_name=g.document_name,
                            detail=sha,
                        )
                        for g in group
                    ],
                    extra_fp=sha,
                )
            )

        # Near-duplicates via perceptual hash (threshold: Hamming ≤ 8 on 64-bit dHash)
        for i in range(len(perceptual)):
            for j in range(i + 1, len(perceptual)):
                a_doc, a_h = perceptual[i]
                b_doc, b_h = perceptual[j]
                if a_doc.sha256 and a_doc.sha256 == b_doc.sha256:
                    continue  # exact dup already reported
                dist = _hamming(a_h, b_h)
                if dist <= 8:
                    indicators.append(
                        self._indicator(
                            code=ForensicsIndicatorCode.NEAR_DUPLICATE,
                            risk=ForensicsRiskClass.POSSIBLE_DUPLICATE,
                            severity=FindingSeverity.MANUAL_REVIEW,
                            title="Near-duplicate document visuals",
                            description=(
                                f"Perceptual hash distance {dist} between "
                                f"'{a_doc.document_name}' and '{b_doc.document_name}'. "
                                "May be a rescanned/recompressed copy — not fraud."
                            ),
                            doc=a_doc,
                            verification=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                            evidence=[
                                ForensicsEvidenceDraft(
                                    description=f"{a_doc.document_name} dHash={a_h}",
                                    document_id=a_doc.document_id,
                                    document_name=a_doc.document_name,
                                ),
                                ForensicsEvidenceDraft(
                                    description=f"{b_doc.document_name} dHash={b_h}",
                                    document_id=b_doc.document_id,
                                    document_name=b_doc.document_name,
                                ),
                            ],
                            extra_fp=f"{a_h}:{b_h}:{dist}",
                        )
                    )

        fp_parts = [d.sha256 or d.document_id for d in sorted(docs, key=lambda x: x.document_id)]
        for ind in indicators:
            fp_parts.append(ind.fingerprint)
        return ForensicsCompareResult(
            indicators=indicators,
            limitations=limitations,
            input_fingerprint=_fp(*fp_parts),
            module_result=cap,
        )

    def _indicator(
        self,
        *,
        code: ForensicsIndicatorCode,
        risk: ForensicsRiskClass,
        severity: FindingSeverity,
        title: str,
        description: str,
        doc: Optional[DocForensicsInput],
        verification: VerificationStatus,
        evidence: Optional[list[ForensicsEvidenceDraft]] = None,
        pages: Optional[list[int]] = None,
        metadata: Optional[dict[str, Any]] = None,
        extra_fp: str = "",
    ) -> ForensicsIndicatorDraft:
        doc_id = doc.document_id if doc else ""
        draft = ForensicsIndicatorDraft(
            code=code,
            risk_class=risk,
            severity=severity,
            title=title,
            description=description,
            document_id=doc.document_id if doc else None,
            document_name=doc.document_name if doc else None,
            affected_pages=pages or [],
            verification_status=verification,
            evidence=evidence or [],
            metadata=metadata or {},
            fingerprint=_fp(code.value, doc_id, title, extra_fp),
        )
        return draft

    def _analyze_pdf(self, doc: DocForensicsInput, content: bytes) -> list[ForensicsIndicatorDraft]:
        out: list[ForensicsIndicatorDraft] = []
        header = _PDF_HEADER.match(content[:16])
        if not header:
            # Magic bytes said PDF earlier but header missing → malformed
            if content[:4] != b"%PDF":
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.MALFORMED_STRUCTURE,
                        risk=ForensicsRiskClass.TECHNICAL_ANOMALY,
                        severity=FindingSeverity.WARNING,
                        title="PDF header missing or malformed",
                        description=(
                            f"File '{doc.document_name}' does not start with a valid %PDF- header. "
                            "Technical anomaly — not a confirmed authenticity failure or fraud."
                        ),
                        doc=doc,
                        verification=VerificationStatus.MISMATCH_DETECTED,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"First bytes: {content[:8]!r}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                    )
                )
                return out

        try:
            import fitz
        except ImportError:
            out.append(
                self._indicator(
                    code=ForensicsIndicatorCode.UNSUPPORTED_FORMAT,
                    risk=ForensicsRiskClass.CHECK_LIMITATION,
                    severity=FindingSeverity.INFO,
                    title="PDF analyzer unavailable",
                    description="PyMuPDF is not installed; PDF forensics skipped.",
                    doc=doc,
                    verification=VerificationStatus.SOURCE_UNAVAILABLE,
                )
            )
            return out

        try:
            pdf = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            out.append(
                self._indicator(
                    code=ForensicsIndicatorCode.CORRUPT_UNREADABLE,
                    risk=ForensicsRiskClass.TECHNICAL_ANOMALY,
                    severity=FindingSeverity.WARNING,
                    title="PDF could not be opened",
                    description=(
                        f"PyMuPDF failed to open '{doc.document_name}': {exc}. "
                        "May be corrupted or encrypted beyond local capability — not labeled fraud."
                    ),
                    doc=doc,
                    verification=VerificationStatus.MISMATCH_DETECTED,
                    evidence=[
                        ForensicsEvidenceDraft(
                            description=str(exc),
                            document_id=doc.document_id,
                            document_name=doc.document_name,
                        )
                    ],
                )
            )
            return out

        try:
            if pdf.is_encrypted:
                # Try empty password — still report encryption as limitation / anomaly
                auth = False
                try:
                    auth = bool(pdf.authenticate(""))
                except Exception:
                    auth = False
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.ENCRYPTION_DETECTED,
                        risk=ForensicsRiskClass.CHECK_LIMITATION
                        if auth
                        else ForensicsRiskClass.TECHNICAL_ANOMALY,
                        severity=FindingSeverity.WARNING,
                        title="Encrypted PDF detected",
                        description=(
                            f"'{doc.document_name}' is encrypted"
                            + (" (opened with empty password)." if auth else ".")
                            + " Encryption alone is not proof of tampering."
                        ),
                        doc=doc,
                        verification=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"is_encrypted=True; empty_password_ok={auth}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                        metadata={"authenticated": auth},
                    )
                )
                if not auth:
                    return out

            meta = pdf.metadata or {}
            created = _parse_pdf_date(meta.get("creationDate") or meta.get("created"))
            modified = _parse_pdf_date(meta.get("modDate") or meta.get("modified"))

            # Missing metadata → limitation, not tampering
            if not any(meta.get(k) for k in ("creator", "producer", "creationDate", "modDate", "author", "title")):
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.METADATA_ANOMALY,
                        risk=ForensicsRiskClass.CHECK_LIMITATION,
                        severity=FindingSeverity.INFO,
                        title="PDF metadata largely absent",
                        description=(
                            f"'{doc.document_name}' has little or no standard PDF metadata. "
                            "Missing metadata does not automatically imply tampering."
                        ),
                        doc=doc,
                        verification=VerificationStatus.VERIFICATION_PENDING,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"metadata keys present: {[k for k, v in meta.items() if v]}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                                detail=str({k: v for k, v in meta.items() if v}),
                            )
                        ],
                    )
                )
            elif created and modified and modified < created:
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.UNUSUAL_MODIFICATION,
                        risk=ForensicsRiskClass.TECHNICAL_ANOMALY,
                        severity=FindingSeverity.MANUAL_REVIEW,
                        title="Modification date precedes creation date",
                        description=(
                            f"PDF metadata for '{doc.document_name}' has modDate earlier than "
                            "creationDate. Technical anomaly requiring officer review — not fraud."
                        ),
                        doc=doc,
                        verification=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"creationDate={meta.get('creationDate')}; modDate={meta.get('modDate')}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                        metadata={"creationDate": meta.get("creationDate"), "modDate": meta.get("modDate")},
                    )
                )
            elif created and modified and (modified - created).days > 3650:
                # >10 years between create and modify — unusual but not fraud
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.UNUSUAL_MODIFICATION,
                        risk=ForensicsRiskClass.TECHNICAL_ANOMALY,
                        severity=FindingSeverity.INFO,
                        title="Large gap between creation and modification dates",
                        description=(
                            f"'{doc.document_name}' metadata spans {(modified - created).days} days "
                            "between creation and modification. Informational technical signal only."
                        ),
                        doc=doc,
                        verification=VerificationStatus.VERIFICATION_PENDING,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"creation={created.isoformat()}; modified={modified.isoformat()}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                    )
                )

            # Producer/Creator spoofing heuristics: empty creator but exotic producer strings
            producer = (meta.get("producer") or "").strip()
            creator = (meta.get("creator") or "").strip()
            suspicious_tokens = ("crack", "fake", "hack", "nullsoft", "edited with")
            blob = f"{producer} {creator}".lower()
            if any(t in blob for t in suspicious_tokens):
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.METADATA_ANOMALY,
                        risk=ForensicsRiskClass.TECHNICAL_ANOMALY,
                        severity=FindingSeverity.MANUAL_REVIEW,
                        title="Suspicious PDF producer/creator metadata",
                        description=(
                            f"Producer/creator metadata on '{doc.document_name}' contains unusual "
                            "tokens. Technical anomaly for review — not a confirmed authenticity failure."
                        ),
                        doc=doc,
                        verification=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"creator={creator!r}; producer={producer!r}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                    )
                )

            # Structure: xref length vs page count sanity
            try:
                xref_len = pdf.xref_length()
                page_count = pdf.page_count
                if xref_len < max(5, page_count):
                    out.append(
                        self._indicator(
                            code=ForensicsIndicatorCode.MALFORMED_STRUCTURE,
                            risk=ForensicsRiskClass.TECHNICAL_ANOMALY,
                            severity=FindingSeverity.WARNING,
                            title="Unusual PDF cross-reference size",
                            description=(
                                f"xref_length={xref_len} with page_count={page_count} on "
                                f"'{doc.document_name}'. May indicate a truncated or unusual PDF. "
                                "Technical anomaly — not fraud."
                            ),
                            doc=doc,
                            verification=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                            pages=list(range(1, min(page_count, 3) + 1)),
                            evidence=[
                                ForensicsEvidenceDraft(
                                    description=f"xref_length={xref_len}; pages={page_count}",
                                    document_id=doc.document_id,
                                    document_name=doc.document_name,
                                )
                            ],
                        )
                    )
            except Exception:
                pass

            # Digital signatures
            sig_widgets = 0
            try:
                for page_index in range(pdf.page_count):
                    page = pdf.load_page(page_index)
                    widgets = page.widgets() or []
                    for w in widgets:
                        try:
                            if int(w.field_type) == int(getattr(fitz, "PDF_WIDGET_TYPE_SIGNATURE", 7)):
                                sig_widgets += 1
                        except Exception:
                            continue
            except Exception:
                sig_widgets = 0

            sigflags = 0
            try:
                # PyMuPDF returns -1 when signature flags are not applicable.
                raw_flags = pdf.get_sigflags()
                sigflags = int(raw_flags) if raw_flags is not None and int(raw_flags) >= 0 else 0
            except Exception:
                sigflags = 0

            if sig_widgets == 0 and sigflags == 0:
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.SIGNATURE_ABSENT,
                        risk=ForensicsRiskClass.CHECK_LIMITATION,
                        severity=FindingSeverity.INFO,
                        title="No digital signature detected",
                        description=(
                            f"'{doc.document_name}' has no detectable digital signature fields. "
                            "An unsigned PDF is common and does not automatically imply tampering."
                        ),
                        doc=doc,
                        verification=VerificationStatus.VERIFICATION_PENDING,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description="sigflags=0; signature_widgets=0",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                    )
                )
            else:
                # Presence noted; cryptographic validation of cert chain is not fully available
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.SIGNATURE_PRESENT,
                        risk=ForensicsRiskClass.INFORMATIONAL,
                        severity=FindingSeverity.INFO,
                        title="Digital signature field(s) present",
                        description=(
                            f"Detected signature widgets/flags on '{doc.document_name}' "
                            f"(widgets={sig_widgets}, sigflags={sigflags}). "
                            "Full certificate-chain validation against a trusted CA is not "
                            "configured in this deployment — presence ≠ verified authenticity."
                        ),
                        doc=doc,
                        verification=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"sigflags={sigflags}; widgets={sig_widgets}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                        metadata={"sigflags": sigflags, "widgets": sig_widgets},
                    )
                )
                # Heuristic: sigflags bit 1 = signatures exist; bit 2 often means invalid/broken
                if sigflags & 2:
                    out.append(
                        self._indicator(
                            code=ForensicsIndicatorCode.SIGNATURE_INVALID,
                            risk=ForensicsRiskClass.AUTHENTICITY_CONCERN,
                            severity=FindingSeverity.MANUAL_REVIEW,
                            title="PDF signature flags indicate a problem",
                            description=(
                                f"sigflags={sigflags} on '{doc.document_name}' suggests signatures "
                                "may be invalid or the document was modified after signing. "
                                "Authenticity concern for officer review — not an automatic fraud label."
                            ),
                            doc=doc,
                            verification=VerificationStatus.MISMATCH_DETECTED,
                            evidence=[
                                ForensicsEvidenceDraft(
                                    description=f"PDF sigflags bit1 set (value={sigflags})",
                                    document_id=doc.document_id,
                                    document_name=doc.document_name,
                                )
                            ],
                        )
                    )

            # QR: optional pyzbar on first page render
            out.extend(self._check_qr(doc, pdf))

            # If nothing concerning beyond absent signature / empty metadata, add clean_scan once
            concerning = {
                ForensicsIndicatorCode.MALFORMED_STRUCTURE,
                ForensicsIndicatorCode.UNUSUAL_MODIFICATION,
                ForensicsIndicatorCode.SIGNATURE_INVALID,
                ForensicsIndicatorCode.CORRUPT_UNREADABLE,
                ForensicsIndicatorCode.ENCRYPTION_DETECTED,
            }
            if not any(i.code in concerning for i in out):
                out.append(
                    self._indicator(
                        code=ForensicsIndicatorCode.CLEAN_SCAN,
                        risk=ForensicsRiskClass.INFORMATIONAL,
                        severity=FindingSeverity.INFO,
                        title="No high-risk PDF forensic indicators",
                        description=(
                            f"Local scan of '{doc.document_name}' found no high-risk structural "
                            "or signature-flag anomalies. This is not a certification of authenticity."
                        ),
                        doc=doc,
                        verification=VerificationStatus.VERIFIED_BY_SOURCE,
                        evidence=[
                            ForensicsEvidenceDraft(
                                description=f"pages={pdf.page_count}; local forensics engine={ENGINE_VERSION}",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                            )
                        ],
                    )
                )
        finally:
            pdf.close()

        return out

    def _check_qr(self, doc: DocForensicsInput, pdf) -> list[ForensicsIndicatorDraft]:
        try:
            from PIL import Image
            from pyzbar.pyzbar import decode as zbar_decode
        except ImportError:
            return [
                self._indicator(
                    code=ForensicsIndicatorCode.QR_CHECK_UNAVAILABLE,
                    risk=ForensicsRiskClass.CHECK_LIMITATION,
                    severity=FindingSeverity.INFO,
                    title="QR verification unavailable",
                    description=(
                        "QR decode library is not installed in this deployment. "
                        "Absence of a QR check is not a tamper indicator."
                    ),
                    doc=doc,
                    verification=VerificationStatus.SOURCE_UNAVAILABLE,
                )
            ]

        found = 0
        try:
            import fitz

            page = pdf.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            codes = zbar_decode(img)
            found = len(codes)
        except Exception:
            return [
                self._indicator(
                    code=ForensicsIndicatorCode.QR_CHECK_UNAVAILABLE,
                    risk=ForensicsRiskClass.CHECK_LIMITATION,
                    severity=FindingSeverity.INFO,
                    title="QR scan failed",
                    description="Could not render/decode page for QR analysis. Not a tamper finding.",
                    doc=doc,
                    verification=VerificationStatus.SOURCE_UNAVAILABLE,
                    pages=[1],
                )
            ]

        if found == 0:
            return [
                self._indicator(
                    code=ForensicsIndicatorCode.QR_NOT_FOUND,
                    risk=ForensicsRiskClass.INFORMATIONAL,
                    severity=FindingSeverity.INFO,
                    title="No QR code detected on first page",
                    description=(
                        "No QR symbology detected on page 1. Many genuine documents have no QR code."
                    ),
                    doc=doc,
                    verification=VerificationStatus.VERIFICATION_PENDING,
                    pages=[1],
                )
            ]

        return [
            self._indicator(
                code=ForensicsIndicatorCode.QR_DETECTED_UNVERIFIED,
                risk=ForensicsRiskClass.CHECK_LIMITATION,
                severity=FindingSeverity.INFO,
                title="QR code detected — claim not verified against authority",
                description=(
                    f"Found {found} QR code(s) on page 1 of '{doc.document_name}'. "
                    "No authorised live verification endpoint is configured; payload is not "
                    "validated against an issuing authority. Simulated/unavailable — not fraud."
                ),
                doc=doc,
                verification=VerificationStatus.SOURCE_UNAVAILABLE,
                pages=[1],
                evidence=[
                    ForensicsEvidenceDraft(
                        description=f"{found} QR code(s) on page 1; external verify unavailable",
                        document_id=doc.document_id,
                        document_name=doc.document_name,
                        page_number=1,
                        page_reference="p.1",
                    )
                ],
            )
        ]

    def _analyze_image(self, doc: DocForensicsInput, content: bytes) -> list[ForensicsIndicatorDraft]:
        out: list[ForensicsIndicatorDraft] = []
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception as exc:
            out.append(
                self._indicator(
                    code=ForensicsIndicatorCode.CORRUPT_UNREADABLE,
                    risk=ForensicsRiskClass.TECHNICAL_ANOMALY,
                    severity=FindingSeverity.WARNING,
                    title="Image failed integrity open/verify",
                    description=(
                        f"'{doc.document_name}' could not be verified as a valid image ({exc}). "
                        "Technical anomaly — not labeled fraud."
                    ),
                    doc=doc,
                    verification=VerificationStatus.MISMATCH_DETECTED,
                )
            )
            return out

        out.append(
            self._indicator(
                code=ForensicsIndicatorCode.CLEAN_SCAN,
                risk=ForensicsRiskClass.INFORMATIONAL,
                severity=FindingSeverity.INFO,
                title="Image opened successfully",
                description=(
                    f"'{doc.document_name}' opens as a valid raster image. "
                    "No PDF signature/metadata checks apply. Not a certification of authenticity."
                ),
                doc=doc,
                verification=VerificationStatus.VERIFIED_BY_SOURCE,
            )
        )
        out.append(
            self._indicator(
                code=ForensicsIndicatorCode.SIGNATURE_ABSENT,
                risk=ForensicsRiskClass.CHECK_LIMITATION,
                severity=FindingSeverity.INFO,
                title="No digital signature applicable to raster image",
                description=(
                    "Raster images do not carry PDF-style digital signatures. "
                    "Absence of a signature is expected and not tampering."
                ),
                doc=doc,
                verification=VerificationStatus.VERIFICATION_PENDING,
            )
        )
        return out

    def _pdf_page_dhash(self, content: bytes) -> Optional[str]:
        try:
            import fitz
            from PIL import Image

            pdf = fitz.open(stream=content, filetype="pdf")
            try:
                if pdf.is_encrypted and not pdf.authenticate(""):
                    return None
                if pdf.page_count < 1:
                    return None
                page = pdf.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                return _dhash_hex(img)
            finally:
                pdf.close()
        except Exception:
            return None


# Keep the historical name as an alias for imports that expect the stub.
class UnavailableForensicsModule(LocalForensicsModule):
    """Backward-compatible alias — now delegates to LocalForensicsModule."""
