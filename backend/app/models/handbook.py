"""Verified AICTE Approval Process Handbook references.

The repository ships NO handbook citations: clause numbers can only be entered by an
administrator after checking the official handbook. A reference is shown to officers as
"verified" only when edition, section and page are all present AND an administrator marked it
verified. Anything else is displayed as unverified — a reference is never invented.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UTCDateTime, new_id


class HandbookReference(Base, TimestampMixin):
    __tablename__ = "handbook_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Rule code (e.g. SYN-RULE-001) or "<config_code>:<check_code>" for document checks.
    reference_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    edition: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    section: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    page: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Optional scope. Empty means "not limited to one year or application type".
    # These never invent a clause — they only record what the administrator entered.
    academic_year: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    applicable_categories: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
