from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UTCDateTime, enum_type, new_id
from app.models.category import ApplicationCategory
from app.models.enums import ApplicationStatus, Priority
from app.models.user import Institution, User


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (Index("ix_applications_institution_status", "institution_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    institution_id: Mapped[str] = mapped_column(
        ForeignKey("institutions.id"), index=True, nullable=False
    )
    category_id: Mapped[str] = mapped_column(
        ForeignKey("application_categories.id"), index=True, nullable=False
    )
    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_officer_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )

    program_name: Mapped[str] = mapped_column(String(255), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(16), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    status: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus), index=True, default=ApplicationStatus.DRAFT, nullable=False
    )
    priority: Mapped[Priority] = mapped_column(
        enum_type(Priority), default=Priority.LOW, nullable=False
    )
    # Demo prioritisation aid only - not proof of fraud or compliance / auto-rejection.
    priority_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_config_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scrutiny_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    requires_manual_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deficiency_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    last_transition_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    last_transition_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship()
    category: Mapped[ApplicationCategory] = relationship()
    created_by: Mapped[Optional[User]] = relationship(foreign_keys=[created_by_id])
    assigned_officer: Mapped[Optional[User]] = relationship(foreign_keys=[assigned_officer_id])
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        back_populates="application", cascade="all, delete-orphan", order_by="Document.created_at"
    )
