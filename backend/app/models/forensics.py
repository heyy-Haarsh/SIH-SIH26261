"""Persisted authenticity / tamper-risk analysis runs and indicators."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import (
    FindingSeverity,
    ForensicsIndicatorCode,
    ForensicsIndicatorStatus,
    ForensicsRiskClass,
    ForensicsRunStatus,
    VerificationStatus,
)


class ForensicsRun(Base):
    __tablename__ = "forensics_runs"
    __table_args__ = (Index("ix_forensics_runs_app_created", "application_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    validation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ForensicsRunStatus] = mapped_column(
        enum_type(ForensicsRunStatus), default=ForensicsRunStatus.QUEUED, nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(32), default="validation", nullable=False)
    triggered_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    engine_version: Mapped[str] = mapped_column(String(64), default="forensics-0.1", nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    limitations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    indicators: Mapped[list["ForensicsIndicator"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ForensicsIndicator.created_at",
    )


class ForensicsIndicator(Base):
    """One explainable authenticity / tamper-risk signal.

    Never stores an outcome of 'fraud'. Open indicators are fingerprint-deduped on reruns.
    """

    __tablename__ = "forensics_indicators"
    __table_args__ = (
        Index("ix_forensics_ind_app_code", "application_id", "code"),
        Index("ix_forensics_ind_app_fp", "application_id", "fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("forensics_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True, nullable=True
    )
    code: Mapped[ForensicsIndicatorCode] = mapped_column(
        enum_type(ForensicsIndicatorCode), nullable=False, index=True
    )
    risk_class: Mapped[ForensicsRiskClass] = mapped_column(
        enum_type(ForensicsRiskClass), nullable=False, index=True
    )
    original_risk_class: Mapped[ForensicsRiskClass] = mapped_column(
        enum_type(ForensicsRiskClass), nullable=False
    )
    severity: Mapped[FindingSeverity] = mapped_column(enum_type(FindingSeverity), nullable=False)
    status: Mapped[ForensicsIndicatorStatus] = mapped_column(
        enum_type(ForensicsIndicatorStatus),
        default=ForensicsIndicatorStatus.OPEN,
        nullable=False,
        index=True,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        enum_type(VerificationStatus),
        default=VerificationStatus.VERIFICATION_PENDING,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_pages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    indicator_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    run: Mapped[ForensicsRun] = relationship(back_populates="indicators")
    evidence: Mapped[list["ForensicsEvidence"]] = relationship(
        back_populates="indicator",
        cascade="all, delete-orphan",
        order_by="ForensicsEvidence.created_at",
    )


class ForensicsEvidence(Base):
    __tablename__ = "forensics_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    indicator_id: Mapped[str] = mapped_column(
        ForeignKey("forensics_indicators.id", ondelete="CASCADE"), index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    document_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    indicator: Mapped[ForensicsIndicator] = relationship(back_populates="evidence")
