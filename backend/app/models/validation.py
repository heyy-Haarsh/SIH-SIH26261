from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import (
    FindingSeverity,
    FindingStatus,
    ValidationOutcome,
    ValidationRunStatus,
)


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    __table_args__ = (Index("ix_validation_runs_app_created", "application_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ValidationRunStatus] = mapped_column(
        enum_type(ValidationRunStatus), default=ValidationRunStatus.QUEUED, nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    triggered_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    engine_version: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="validation_run", cascade="all, delete-orphan", order_by="Finding.created_at"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True, nullable=True
    )
    rule_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regulatory_rules.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Snapshots so history stays meaningful if a rule changes later
    rule_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rule_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rule_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    handbook_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        enum_type(FindingSeverity), index=True, nullable=False
    )
    status: Mapped[FindingStatus] = mapped_column(
        enum_type(FindingStatus), default=FindingStatus.OPEN, nullable=False
    )
    outcome: Mapped[ValidationOutcome] = mapped_column(enum_type(ValidationOutcome), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    validation_run: Mapped[ValidationRun] = relationship(back_populates="findings")
    evidence: Mapped[list["FindingEvidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan", order_by="FindingEvidence.created_at"
    )


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    document_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_reference: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    rule_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rule_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="evidence")
