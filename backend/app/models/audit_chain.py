"""Append-only hash-chained audit events (separate from human-readable AuditEvent)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UTCDateTime, new_id, utcnow


class AuditChainEvent(Base):
    __tablename__ = "audit_chain_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sequence: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    application_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    rule_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    connector_used: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="REAL")
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    result_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    chain_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
