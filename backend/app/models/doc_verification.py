"""Phase 7: per-document three-layer verification runs and evidence checks."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import (
    DocumentReviewStatus,
    DocumentVerificationRunStatus,
    ExternalVerificationLayerStatus,
    RuleValidationStatus,
    VerificationCheckLayer,
    VerificationSource,
)


class DocumentVerificationRun(Base):
    """One execution of the three-layer pipeline for a document version."""

    __tablename__ = "document_verification_runs"
    __table_args__ = (
        Index("ix_docverif_run_app", "application_id", "created_at"),
        Index("ix_docverif_run_doc", "document_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    validation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="SET NULL"), nullable=True
    )
    config_code: Mapped[str] = mapped_column(String(64), nullable=False)
    config_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[DocumentVerificationRunStatus] = mapped_column(
        enum_type(DocumentVerificationRunStatus),
        default=DocumentVerificationRunStatus.QUEUED,
        nullable=False,
    )
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
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    limitations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    scrutiny_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    triggered_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    checks: Mapped[list["DocumentVerificationCheck"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="DocumentVerificationCheck.created_at"
    )


class DocumentVerificationCheck(Base):
    """Single Layer 1/2/3 check with source, evidence, and limitations."""

    __tablename__ = "document_verification_checks"
    __table_args__ = (Index("ix_docverif_check_run_layer", "run_id", "layer"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("document_verification_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    layer: Mapped[VerificationCheckLayer] = mapped_column(
        enum_type(VerificationCheckLayer), nullable=False
    )
    check_code: Mapped[str] = mapped_column(String(96), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Outcome uses VerificationStatus for Layer 2; Layer 1 uses severity-like strings in outcome_label
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="info", nullable=False)
    source: Mapped[VerificationSource] = mapped_column(
        enum_type(VerificationSource), default=VerificationSource.LOCAL_VALIDATION, nullable=False
    )
    adapter: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    is_synthetic_rule: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    limitations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)  # open|resolved|waived|accepted
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    run: Mapped[DocumentVerificationRun] = relationship(back_populates="checks")
