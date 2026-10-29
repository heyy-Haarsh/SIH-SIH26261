from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UTCDateTime, new_id, utcnow


class Notification(Base):
    """An in-app notification for one user. Email/SMS delivery is not implemented."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    application_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # Frontend path to open when the notification is clicked.
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, index=True, nullable=False
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
