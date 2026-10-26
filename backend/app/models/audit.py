from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UTCDateTime, new_id, utcnow


class AuditEvent(Base):
    """Append-only audit trail. Rows are never updated or deleted by application code."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_app_created", "application_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(255), default="system", nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, index=True, nullable=False
    )
