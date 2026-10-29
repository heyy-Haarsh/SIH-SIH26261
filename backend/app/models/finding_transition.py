from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UTCDateTime, new_id, utcnow


class FindingTransition(Base):
    """Append-only history of every status change of a finding (who, when, why)."""

    __tablename__ = "finding_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(128), default="system", nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True, nullable=False)


class DeficiencyFinding(Base):
    """Links a clarification request to every finding it covers (one request, many findings)."""

    __tablename__ = "deficiency_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deficiency_id: Mapped[str] = mapped_column(
        ForeignKey("deficiency_notices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
