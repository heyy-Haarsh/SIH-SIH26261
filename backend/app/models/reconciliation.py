"""Persisted cross-document reconciliation runs and findings."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import (
    FindingSeverity,
    ReconciliationItemStatus,
    ReconciliationOutcome,
    ReconciliationRunStatus,
)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    __table_args__ = (Index("ix_recon_runs_app_created", "application_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    validation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ReconciliationRunStatus] = mapped_column(
        enum_type(ReconciliationRunStatus),
        default=ReconciliationRunStatus.QUEUED,
        nullable=False,
    )
    trigger: Mapped[str] = mapped_column(String(32), default="validation", nullable=False)
    triggered_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    engine_version: Mapped[str] = mapped_column(String(64), default="reconciliation-0.1", nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    items: Mapped[list["ReconciliationItem"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ReconciliationItem.created_at",
    )


class ReconciliationItem(Base):
    """One field-level (or duplicate-doc) comparison result for an application.

    Open items are deduplicated by fingerprint in the reconciliation service so
    reruns do not create duplicate findings. Resolutions preserve the original row.
    """

    __tablename__ = "reconciliation_items"
    __table_args__ = (
        Index("ix_recon_items_app_field", "application_id", "field_name"),
        Index("ix_recon_items_app_fp", "application_id", "fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[ReconciliationOutcome] = mapped_column(
        enum_type(ReconciliationOutcome), nullable=False, index=True
    )
    original_outcome: Mapped[ReconciliationOutcome] = mapped_column(
        enum_type(ReconciliationOutcome), nullable=False
    )
    match_kind: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    severity: Mapped[FindingSeverity] = mapped_column(enum_type(FindingSeverity), nullable=False)
    status: Mapped[ReconciliationItemStatus] = mapped_column(
        enum_type(ReconciliationItemStatus),
        default=ReconciliationItemStatus.OPEN,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    run: Mapped[ReconciliationRun] = relationship(back_populates="items")
    values: Mapped[list["ReconciliationValue"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ReconciliationValue.document_name",
    )


class ReconciliationValue(Base):
    """Per-document evidence linked to a reconciliation item."""

    __tablename__ = "reconciliation_values"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_field_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("extracted_fields.id", ondelete="SET NULL"), nullable=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    evidence_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    item: Mapped[ReconciliationItem] = relationship(back_populates="values")
