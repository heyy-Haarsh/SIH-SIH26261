"""Extraction runs and field-level provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import (
    DocumentContentKind,
    ExtractionMethod,
    ExtractionRunStatus,
    FieldReviewStatus,
    SemanticDocumentCategory,
)


class ExtractionRun(Base):
    """One processing attempt for a specific document version + config fingerprint."""

    __tablename__ = "extraction_runs"
    __table_args__ = (
        Index("ix_extraction_runs_docver_created", "document_version_id", "created_at"),
        UniqueConstraint(
            "document_version_id",
            "content_sha256",
            "config_fingerprint",
            name="uq_extraction_idempotent",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    validation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ExtractionRunStatus] = mapped_column(
        enum_type(ExtractionRunStatus), default=ExtractionRunStatus.QUEUED, nullable=False, index=True
    )
    content_kind: Mapped[DocumentContentKind] = mapped_column(
        enum_type(DocumentContentKind), default=DocumentContentKind.UNSUPPORTED, nullable=False
    )
    selected_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    predicted_category: Mapped[SemanticDocumentCategory] = mapped_column(
        enum_type(SemanticDocumentCategory),
        default=SemanticDocumentCategory.UNKNOWN,
        nullable=False,
    )
    category_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    category_method: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    category_signals: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    category_mismatch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    engine_version: Mapped[str] = mapped_column(String(64), default="extraction-0.1", nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pages_with_text: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_ocr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stage_timings_ms: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ocr_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ocr_languages: Mapped[str] = mapped_column(String(64), default="eng", nullable=False)

    triggered_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    document_version: Mapped["DocumentVersion"] = relationship(  # noqa: F821
        back_populates="extraction_runs"
    )
    fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="extraction_run", cascade="all, delete-orphan"
    )
