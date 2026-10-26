"""Persisted administrator configuration (verification + runtime flags).

Secrets are never stored here — only non-sensitive toggles and limits.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from app.core.database import Base
from app.models.base import UTCDateTime, new_id, utcnow


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(96), unique=True, index=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    change_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
