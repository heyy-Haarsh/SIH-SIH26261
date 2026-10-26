from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.application import Application
from app.models.base import TimestampMixin, UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import (
    DocumentReviewStatus,
    DocumentStatus,
    ExtractionMethod,
    ExternalVerificationLayerStatus,
    FieldReviewStatus,
    RuleValidationStatus,
    ValidationOutcome,
)


class Document(Base, TimestampMixin):
    """One logical document per (application, requirement); versions hold the files.

    Phase 7 three-layer statuses are independent: Layer 1 pass never implies authenticity.
    """

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("application_id", "requirement_code", name="uq_doc_app_req"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirement_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_type(DocumentStatus), default=DocumentStatus.UPLOADED, nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Latest three-layer snapshot (updated by verification pipeline; not proof of authenticity)
    rule_validation_status: Mapped[RuleValidationStatus] = mapped_column(
        enum_type(RuleValidationStatus), default=RuleValidationStatus.PENDING, nullable=False
    )
    external_verification_status: Mapped[ExternalVerificationLayerStatus] = mapped_column(
        enum_type(ExternalVerificationLayerStatus),
        default=ExternalVerificationLayerStatus.PENDING,
        nullable=False,
    )
    review_status: Mapped[DocumentReviewStatus] = mapped_column(
        enum_type(DocumentReviewStatus), default=DocumentReviewStatus.PENDING, nullable=False
    )
    latest_verification_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    application: Mapped[Application] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version",
    )

    @property
    def latest_version(self) -> Optional["DocumentVersion"]:
        return self.versions[-1] if self.versions else None


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_docver_doc_version"),
        Index("ix_docver_sha256", "sha256"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    declared_content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_checks: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    validation_outcome: Mapped[ValidationOutcome] = mapped_column(
        enum_type(ValidationOutcome), default=ValidationOutcome.PENDING, nullable=False
    )
    uploaded_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    document: Mapped[Document] = relationship(back_populates="versions")
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(  # noqa: F821
        back_populates="document_version", cascade="all, delete-orphan"
    )


class ExtractedField(Base):
    """Field extracted from a document version, optionally tied to an extraction run."""

    __tablename__ = "extracted_fields"
    __table_args__ = (Index("ix_extracted_fields_run_name", "extraction_run_id", "field_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    extraction_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), index=True, nullable=True
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Display value (prefer normalized when safe)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Field-extraction confidence only when the method supplies a defensible score; never fabricated for regex.
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Bounding box in PDF page coordinate space (origin top-left of page, units = PDF points).
    # Convention documented in docs/EXTRACTION.md. Null when location unknown — never fabricated.
    bbox_x0: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y0: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_x1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    coordinate_space: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    method: Mapped[ExtractionMethod] = mapped_column(
        enum_type(ExtractionMethod), default=ExtractionMethod.TEXT_KEY_VALUE, nullable=False
    )
    review_status: Mapped[FieldReviewStatus] = mapped_column(
        enum_type(FieldReviewStatus), default=FieldReviewStatus.PENDING, nullable=False
    )
    corrected_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_conflict: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    candidate_values: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    document_version: Mapped[DocumentVersion] = relationship(back_populates="extracted_fields")
    extraction_run: Mapped[Optional["ExtractionRun"]] = relationship(  # noqa: F821
        back_populates="fields"
    )
