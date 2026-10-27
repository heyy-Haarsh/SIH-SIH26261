"""ExtractionOrchestrator — upload → inspect → extract → fields → persist."""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.document_processing.evidence_mapper import EvidenceMapper
from app.document_processing.field_extractor import FieldExtractor
from app.document_processing.inspector import DocumentInspector, MIN_TEXT_CHARS_PER_PAGE
from app.document_processing.intelligence_types import ExtractionOutcome, FieldCandidate, PageText
from app.document_processing.ocr_processor import OCRProcessor
from app.document_processing.pdf_extractor import PDFTextExtractor
from app.document_processing.semantic_classifier import SemanticDocumentClassifier, is_category_mismatch
from app.models.base import utcnow
from app.models.document import DocumentVersion, ExtractedField
from app.models.enums import (
    DocumentContentKind,
    ExtractionMethod,
    ExtractionRunStatus,
    FieldReviewStatus,
    SemanticDocumentCategory,
)
from app.models.extraction import ExtractionRun

logger = logging.getLogger("praman.extraction")

ENGINE_VERSION = "extraction-0.1"


def config_fingerprint() -> str:
    s = get_settings()
    raw = (
        f"{ENGINE_VERSION}|pdf={s.enable_local_pdf_extraction}|ocr={s.enable_local_ocr}|"
        f"langs={s.ocr_languages}|dpi={s.ocr_dpi}|max_pages={s.max_extraction_pages}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ExtractionOrchestrator:
    def __init__(self) -> None:
        self.inspector = DocumentInspector()
        self.pdf = PDFTextExtractor()
        self.ocr = OCRProcessor()
        self.fields = FieldExtractor()
        self.evidence = EvidenceMapper()
        self.semantic = SemanticDocumentClassifier()

    def process_bytes(
        self,
        *,
        content: bytes,
        extension: str,
        file_name: str,
        mime_type: str = "",
        selected_requirement_code: str | None = None,
    ) -> ExtractionOutcome:
        settings = get_settings()
        timings: dict[str, int] = {}
        warnings: list[str] = []

        t0 = time.perf_counter()
        inspect = self.inspector.inspect(content=content, extension=extension, mime_type=mime_type)
        timings["inspect"] = int((time.perf_counter() - t0) * 1000)
        warnings.extend(inspect.warnings)

        if not inspect.readable:
            status = (
                ExtractionRunStatus.UNSUPPORTED
                if inspect.content_kind == DocumentContentKind.UNSUPPORTED
                else ExtractionRunStatus.FAILED
            )
            return ExtractionOutcome(
                status=status,
                content_kind=inspect.content_kind,
                warnings=warnings,
                error_code=inspect.error_code,
                error_message=inspect.error_message,
                stage_timings_ms=timings,
                ocr_available=self.ocr.available,
                ocr_languages=settings.ocr_languages,
                page_count=inspect.page_count,
            )

        pages: list[PageText] = []
        pages_ocr = 0
        pages_with_text = 0
        status = ExtractionRunStatus.COMPLETED

        try:
            if inspect.content_kind == DocumentContentKind.TEXT:
                t0 = time.perf_counter()
                text = content.decode("utf-8", errors="replace")
                pages = [
                    PageText(
                        page_number=1,
                        text=text,
                        source="pdf_text",
                        char_count=len(text.strip()),
                    )
                ]
                timings["text_decode"] = int((time.perf_counter() - t0) * 1000)

            elif inspect.content_kind == DocumentContentKind.IMAGE:
                t0 = time.perf_counter()
                if not self.ocr.available:
                    timings["ocr"] = int((time.perf_counter() - t0) * 1000)
                    logger.warning(
                        "ocr_unavailable_for_image %s",
                        self.ocr.status.get("message") or "OCR unavailable",
                    )
                    return ExtractionOutcome(
                        status=ExtractionRunStatus.OCR_UNAVAILABLE,
                        content_kind=inspect.content_kind,
                        warnings=warnings + [self.ocr.status.get("message", "OCR unavailable")],
                        error_code="ocr_unavailable",
                        error_message=self.ocr.status.get("message") or "OCR is not available.",
                        stage_timings_ms=timings,
                        ocr_available=False,
                        ocr_languages=settings.ocr_languages,
                        page_count=1,
                    )
                pages = [self.ocr.ocr_image_bytes(content)]
                pages_ocr = 1
                timings["ocr"] = int((time.perf_counter() - t0) * 1000)

            elif inspect.content_kind in {
                DocumentContentKind.DIGITAL_PDF,
                DocumentContentKind.SCANNED_PDF,
                DocumentContentKind.MIXED_PDF,
            }:
                pages, pages_ocr, status, extra_warn, pdf_timings = self._process_pdf(
                    content, inspect.content_kind
                )
                timings.update(pdf_timings)
                warnings.extend(extra_warn)

            elif inspect.content_kind == DocumentContentKind.DOCX:
                warnings.append("DOCX structured extraction is limited; no full text pipeline yet.")
                status = ExtractionRunStatus.UNSUPPORTED
                return ExtractionOutcome(
                    status=status,
                    content_kind=inspect.content_kind,
                    warnings=warnings,
                    error_code="docx_limited",
                    error_message="DOCX extraction is not fully implemented in this phase.",
                    stage_timings_ms=timings,
                    ocr_available=self.ocr.available,
                    ocr_languages=settings.ocr_languages,
                )
            else:
                return ExtractionOutcome(
                    status=ExtractionRunStatus.UNSUPPORTED,
                    content_kind=inspect.content_kind,
                    warnings=warnings,
                    error_code="unsupported",
                    error_message="Unsupported document kind for extraction.",
                    stage_timings_ms=timings,
                    ocr_available=self.ocr.available,
                    ocr_languages=settings.ocr_languages,
                )
        except PermissionError:
            return ExtractionOutcome(
                status=ExtractionRunStatus.FAILED,
                content_kind=inspect.content_kind,
                error_code="pdf_encrypted",
                error_message="PDF is password-protected.",
                stage_timings_ms=timings,
                ocr_available=self.ocr.available,
                ocr_languages=settings.ocr_languages,
                page_count=inspect.page_count,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("extraction_failed")
            return ExtractionOutcome(
                status=ExtractionRunStatus.FAILED,
                content_kind=inspect.content_kind,
                error_code="extraction_error",
                error_message=f"Extraction failed ({exc.__class__.__name__}).",
                stage_timings_ms=timings,
                ocr_available=self.ocr.available,
                ocr_languages=settings.ocr_languages,
                page_count=inspect.page_count,
                warnings=warnings,
            )

        pages_with_text = sum(1 for p in pages if p.char_count >= MIN_TEXT_CHARS_PER_PAGE)

        from app.document_processing.clarity import assess_upload

        clarity_note = assess_upload(
            content, inspect.content_kind, pages_with_text=pages_with_text
        )
        if clarity_note:
            warnings.append(clarity_note)
            if status == ExtractionRunStatus.COMPLETED:
                status = ExtractionRunStatus.COMPLETED_WITH_WARNINGS

        t0 = time.perf_counter()
        field_cands = self.fields.extract_from_pages(pages, file_name=file_name)

        # LLM fallback — never pass/fail; only fill missing fields when enabled
        field_cands = self._maybe_llm_fill(
            field_cands, pages=pages, selected_requirement_code=selected_requirement_code
        )
        field_cands = self.evidence.map_fields(field_cands, pages)
        field_cands = self._merge_conflicts(field_cands)
        timings["fields"] = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        semantic = self.semantic.classify(
            file_name=file_name,
            pages=pages,
            selected_requirement_code=selected_requirement_code,
        )
        timings["semantic"] = int((time.perf_counter() - t0) * 1000)

        if warnings and status == ExtractionRunStatus.COMPLETED:
            status = ExtractionRunStatus.COMPLETED_WITH_WARNINGS
        if not pages_with_text and pages_ocr == 0 and status == ExtractionRunStatus.COMPLETED:
            status = ExtractionRunStatus.REQUIRES_MANUAL_REVIEW
            warnings.append("No usable text was extracted from any page.")

        return ExtractionOutcome(
            status=status,
            content_kind=inspect.content_kind,
            pages=pages,
            fields=field_cands,
            semantic=semantic,
            warnings=warnings,
            stage_timings_ms=timings,
            ocr_available=self.ocr.available,
            ocr_languages=settings.ocr_languages,
            page_count=inspect.page_count or len(pages),
            pages_with_text=pages_with_text,
            pages_ocr=pages_ocr,
        )

    def _process_pdf(
        self, content: bytes, kind: DocumentContentKind
    ) -> tuple[list[PageText], int, ExtractionRunStatus, list[str], dict[str, int]]:
        settings = get_settings()
        timings: dict[str, int] = {}
        warnings: list[str] = []
        status = ExtractionRunStatus.COMPLETED
        pages_ocr = 0

        if not self.pdf.available():
            warnings.append("PyMuPDF not available; cannot extract PDF text.")
            return [], 0, ExtractionRunStatus.FAILED, warnings, timings

        t0 = time.perf_counter()
        pages = self.pdf.extract_pages(content, max_pages=settings.max_extraction_pages)
        timings["pdf_text"] = int((time.perf_counter() - t0) * 1000)

        needs_ocr_idx = [
            i for i, p in enumerate(pages) if p.source == "none" or p.char_count < MIN_TEXT_CHARS_PER_PAGE
        ]

        if needs_ocr_idx:
            if not self.ocr.available:
                logger.warning(
                    "ocr_unavailable_for_pdf pages=%s detail=%s",
                    len(needs_ocr_idx),
                    self.ocr.status.get("message") or "OCR unavailable",
                )
                if kind == DocumentContentKind.SCANNED_PDF or len(needs_ocr_idx) == len(pages):
                    status = ExtractionRunStatus.OCR_UNAVAILABLE
                    warnings.append(self.ocr.status.get("message") or "OCR unavailable for scanned pages.")
                else:
                    status = ExtractionRunStatus.COMPLETED_WITH_WARNINGS
                    warnings.append(
                        f"{len(needs_ocr_idx)} page(s) lack text; OCR unavailable — "
                        + (self.ocr.status.get("message") or "install Tesseract to OCR those pages.")
                    )
            else:
                t0 = time.perf_counter()
                for i in needs_ocr_idx:
                    try:
                        ocr_page = self.ocr.ocr_pdf_page(
                            content, i, page_number=pages[i].page_number
                        )
                        pages[i] = ocr_page
                        pages_ocr += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "ocr_page_failed page=%s error=%s",
                            pages[i].page_number,
                            exc.__class__.__name__,
                            exc_info=exc,
                        )
                        warnings.append(
                            f"OCR failed on page {pages[i].page_number}: {exc.__class__.__name__}"
                        )
                        status = ExtractionRunStatus.COMPLETED_WITH_WARNINGS
                timings["ocr"] = int((time.perf_counter() - t0) * 1000)

        if kind == DocumentContentKind.SCANNED_PDF and pages_ocr == 0 and not self.ocr.available:
            status = ExtractionRunStatus.REQUIRES_OCR

        return pages, pages_ocr, status, warnings, timings

    def _maybe_llm_fill(
        self,
        fields: list[FieldCandidate],
        *,
        pages: list[PageText],
        selected_requirement_code: str | None,
    ) -> list[FieldCandidate]:
        settings = get_settings()
        if not settings.enable_ai_extraction:
            return fields
        provider = (settings.llm_provider or "none").strip().lower()
        if provider in ("", "none", "null", "off"):
            return fields
        from app.document_processing.llm_extractor import get_llm_extractor
        from app.document_processing.normalize_text import compute_normalized_value
        from app.verification_engine.loader import get_config_for_requirement

        present = {f.field_name for f in fields if (f.raw_value or "").strip()}
        required: list[str] = []
        if selected_requirement_code:
            cfg = get_config_for_requirement(selected_requirement_code)
            if cfg:
                for item in (cfg.get("layer1") or {}).get("required_fields") or []:
                    if isinstance(item, dict):
                        fname = str(item.get("field") or "").strip()
                    else:
                        fname = str(item).strip()
                    if fname:
                        required.append(fname)
        missing = [r for r in required if r not in present]
        if required and not missing:
            return fields
        schema_keys = missing or required or ["institution_name", "certificate_number"]
        schema = {"properties": {k: {"type": "string"} for k in schema_keys}}
        text_blob = "\n".join(p.text for p in pages if p.text)
        if not text_blob.strip():
            return fields
        extractor = get_llm_extractor()
        extracted = extractor.extract(text_blob, schema)
        out = list(fields)
        for key, val in extracted.items():
            if not isinstance(val, str) or not val.strip():
                continue
            if key in present:
                continue
            out.append(
                FieldCandidate(
                    field_name=str(key),
                    raw_value=val.strip(),
                    normalized_value=compute_normalized_value(val.strip()),
                    method=ExtractionMethod.AI_MODEL,
                    confidence=None,
                    raw_snippet=val.strip()[:240],
                    source="llm",
                )
            )
        return out

    def _merge_conflicts(self, fields: list[FieldCandidate]) -> list[FieldCandidate]:
        grouped: dict[str, list[FieldCandidate]] = defaultdict(list)
        for f in fields:
            grouped[f.field_name].append(f)
        merged: list[FieldCandidate] = []
        for name, items in grouped.items():
            if len(items) == 1:
                merged.append(items[0])
                continue
            primary = items[0]
            # Represent conflict by keeping primary raw and listing candidates;
            # orchestrator persistence sets is_conflict
            primary.normalized_value = None  # do not silently choose among dates
            merged.append(primary)
            for extra in items[1:]:
                # Keep extras only as conflict markers via candidate list on primary
                pass
            # Attach siblings into a synthetic attribute used at persist time
            setattr(primary, "_conflict_siblings", items)
        return merged


def persist_extraction_run(
    db: Session,
    *,
    document_version: DocumentVersion,
    application_id: str,
    outcome: ExtractionOutcome,
    selected_category: str | None,
    content_sha256: str,
    triggered_by_id: str | None,
    reuse_existing: bool = True,
) -> ExtractionRun:
    """Persist outcome idempotently for (version, hash, config)."""
    fp = config_fingerprint()

    existing = (
        db.query(ExtractionRun)
        .filter(
            ExtractionRun.document_version_id == document_version.id,
            ExtractionRun.content_sha256 == content_sha256,
            ExtractionRun.config_fingerprint == fp,
        )
        .first()
    )
    if existing and reuse_existing and existing.status not in {
        ExtractionRunStatus.FAILED,
        ExtractionRunStatus.QUEUED,
        ExtractionRunStatus.RUNNING,
    }:
        return existing
    if existing:
        db.query(ExtractedField).filter(ExtractedField.extraction_run_id == existing.id).delete()
        db.delete(existing)
        db.flush()

    mismatch = False
    predicted = SemanticDocumentCategory.UNKNOWN
    cat_conf = None
    cat_method = ""
    cat_signals: dict = {}
    if outcome.semantic:
        predicted = outcome.semantic.category
        cat_conf = outcome.semantic.confidence
        cat_method = outcome.semantic.method
        cat_signals = outcome.semantic.signals
        mismatch = is_category_mismatch(predicted, selected_category)

    run = ExtractionRun(
        document_version_id=document_version.id,
        application_id=application_id,
        status=outcome.status,
        content_kind=outcome.content_kind,
        selected_category=selected_category,
        predicted_category=predicted,
        category_confidence=cat_conf,
        category_method=cat_method,
        category_signals=cat_signals,
        category_mismatch=mismatch,
        engine_version=ENGINE_VERSION,
        config_fingerprint=fp,
        content_sha256=content_sha256,
        page_count=outcome.page_count,
        pages_with_text=outcome.pages_with_text,
        pages_ocr=outcome.pages_ocr,
        warnings=outcome.warnings,
        error_code=outcome.error_code,
        error_message=outcome.error_message,
        stage_timings_ms=outcome.stage_timings_ms,
        ocr_available=outcome.ocr_available,
        ocr_languages=outcome.ocr_languages,
        triggered_by_id=triggered_by_id,
        started_at=utcnow(),
        completed_at=utcnow(),
    )
    db.add(run)
    db.flush()

    # Clear prior fields for this version from older runs? Keep history — only add for this run.
    for cand in outcome.fields:
        siblings = getattr(cand, "_conflict_siblings", None)
        candidates_payload = []
        is_conflict = False
        if siblings and len(siblings) > 1:
            is_conflict = True
            candidates_payload = [
                {
                    "raw": s.raw_value,
                    "normalized": s.normalized_value,
                    "page": s.page_number,
                    "method": s.method.value,
                }
                for s in siblings
            ]

        # D-20: persist raw exactly; normalized_value is a separate column — never overwrite.
        db.add(
            ExtractedField(
                document_version_id=document_version.id,
                application_id=application_id,
                extraction_run_id=run.id,
                field_name=cand.field_name,
                value=cand.raw_value,
                raw_value=cand.raw_value,
                normalized_value=cand.normalized_value,
                confidence=cand.confidence,
                ocr_confidence=cand.ocr_confidence,
                page_number=cand.page_number,
                page_reference=cand.page_reference,
                bbox_x0=cand.bbox.x0 if cand.bbox else None,
                bbox_y0=cand.bbox.y0 if cand.bbox else None,
                bbox_x1=cand.bbox.x1 if cand.bbox else None,
                bbox_y1=cand.bbox.y1 if cand.bbox else None,
                coordinate_space=cand.bbox.coordinate_space if cand.bbox else None,
                method=cand.method,
                review_status=(
                    FieldReviewStatus.CONFLICT if is_conflict else FieldReviewStatus.PENDING
                ),
                is_conflict=is_conflict,
                candidate_values=candidates_payload,
                unit=cand.unit,
            )
        )

    if document_version.page_count is None and outcome.page_count is not None:
        document_version.page_count = outcome.page_count

    db.flush()
    return run


def run_extraction_for_version(
    db: Session,
    document_version: DocumentVersion,
    *,
    application_id: str,
    selected_requirement_code: str,
    triggered_by_id: str | None,
    force: bool = False,
) -> ExtractionRun:
    path = Path(document_version.storage_path)
    if not path.exists():
        run = ExtractionRun(
            document_version_id=document_version.id,
            application_id=application_id,
            status=ExtractionRunStatus.FAILED,
            content_kind=DocumentContentKind.UNREADABLE,
            selected_category=selected_requirement_code,
            predicted_category=SemanticDocumentCategory.UNKNOWN,
            engine_version=ENGINE_VERSION,
            config_fingerprint=config_fingerprint(),
            content_sha256=document_version.sha256,
            error_code="file_missing",
            error_message="Stored file is missing from disk.",
            warnings=[],
            stage_timings_ms={},
            ocr_available=False,
            triggered_by_id=triggered_by_id,
            started_at=utcnow(),
            completed_at=utcnow(),
        )
        db.add(run)
        db.flush()
        return run

    content = path.read_bytes()
    # Detect content change since upload
    digest = hashlib.sha256(content).hexdigest()
    if digest != document_version.sha256:
        # Do not process mismatched bytes as if they were the uploaded version
        run = ExtractionRun(
            document_version_id=document_version.id,
            application_id=application_id,
            status=ExtractionRunStatus.FAILED,
            content_kind=DocumentContentKind.UNREADABLE,
            selected_category=selected_requirement_code,
            predicted_category=SemanticDocumentCategory.UNKNOWN,
            engine_version=ENGINE_VERSION,
            config_fingerprint=config_fingerprint(),
            content_sha256=digest,
            error_code="content_hash_mismatch",
            error_message="File content no longer matches the recorded upload hash.",
            warnings=[],
            stage_timings_ms={},
            ocr_available=False,
            triggered_by_id=triggered_by_id,
            started_at=utcnow(),
            completed_at=utcnow(),
        )
        db.add(run)
        db.flush()
        return run

    if not force:
        existing = (
            db.query(ExtractionRun)
            .filter(
                ExtractionRun.document_version_id == document_version.id,
                ExtractionRun.content_sha256 == digest,
                ExtractionRun.config_fingerprint == config_fingerprint(),
            )
            .first()
        )
        if existing and existing.status not in {
            ExtractionRunStatus.FAILED,
            ExtractionRunStatus.QUEUED,
            ExtractionRunStatus.RUNNING,
        }:
            return existing

    orch = ExtractionOrchestrator()
    outcome = orch.process_bytes(
        content=content,
        extension=document_version.extension,
        file_name=document_version.file_name,
        mime_type=document_version.mime_type,
        selected_requirement_code=selected_requirement_code,
    )

    if force:
        # Delete prior idempotent row so unique constraint allows insert
        prior = (
            db.query(ExtractionRun)
            .filter(
                ExtractionRun.document_version_id == document_version.id,
                ExtractionRun.content_sha256 == digest,
                ExtractionRun.config_fingerprint == config_fingerprint(),
            )
            .all()
        )
        for p in prior:
            db.query(ExtractedField).filter(ExtractedField.extraction_run_id == p.id).delete()
            db.delete(p)
        db.flush()

    return persist_extraction_run(
        db,
        document_version=document_version,
        application_id=application_id,
        outcome=outcome,
        selected_category=selected_requirement_code,
        content_sha256=digest,
        triggered_by_id=triggered_by_id,
        reuse_existing=not force,
    )
