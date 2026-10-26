from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UTCDateTime, enum_type, new_id, utcnow
from app.models.enums import DeficiencyStatus, ReviewDecisionType, UserRole
from app.models.user import User


class ReviewDecision(Base):
    """A human reviewer's note or decision. Humans decide - the system never auto-decides."""

    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    author_role: Mapped[UserRole] = mapped_column(enum_type(UserRole), nullable=False)
    decision_type: Mapped[ReviewDecisionType] = mapped_column(
        enum_type(ReviewDecisionType), default=ReviewDecisionType.NOTE, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    author: Mapped[User] = relationship()


class DeficiencyNotice(Base):
    __tablename__ = "deficiency_notices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    issued_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    finding_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[DeficiencyStatus] = mapped_column(
        enum_type(DeficiencyStatus), index=True, default=DeficiencyStatus.OPEN, nullable=False
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    applicant_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
