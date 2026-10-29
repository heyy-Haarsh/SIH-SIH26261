"""Issuer document registry — stored authentic records for live verify demos."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UTCDateTime, new_id


class IssuerRegistryRecord(Base, TimestampMixin):
    """A document previously registered by an issuing authority (demo seed or RO entry)."""

    __tablename__ = "issuer_registry_records"
    __table_args__ = (
        Index("ix_issuer_registry_cert", "certificate_number"),
        Index("ix_issuer_registry_doc_type", "doc_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(128), nullable=False)
    issuer_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    holder_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Optional SHA-256 of the canonical issued file (when known).
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="issued", nullable=False)  # issued|revoked
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    issued_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class IssuerVerifyEvent(Base, TimestampMixin):
    """Append-only log of verification calls (great for demo / audit)."""

    __tablename__ = "issuer_verify_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("applications.id"), nullable=True, index=True
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id"), nullable=True, index=True
    )
    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    request_payload: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result: Mapped[str] = mapped_column(String(64), nullable=False)
    response_payload: Mapped[str] = mapped_column(Text, default="", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
