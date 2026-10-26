from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import VerificationSource, VerificationStatus


class VerificationRequest(Base):
    """A claim checked against some source. ``source`` states truthfully where the answer came from."""

    __tablename__ = "verification_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    validation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[VerificationSource] = mapped_column(enum_type(VerificationSource), nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        enum_type(VerificationStatus), nullable=False
    )
    adapter: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    checked_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
