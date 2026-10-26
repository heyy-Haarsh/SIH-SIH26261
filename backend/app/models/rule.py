from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UTCDateTime, new_id, utcnow


class RegulatoryRule(Base, TimestampMixin):
    """A deterministic rule.

    Shipped demo rows are SYNTHETIC (``is_synthetic=True``). Official regulatory
    rules must set ``is_synthetic=False`` and provide a verified source citation —
    never invent AICTE handbook clauses.
    """

    __tablename__ = "regulatory_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    handbook_ref: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    # Required when is_synthetic=False — citation to verified source material only
    verified_source_ref: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    current_version: Mapped[str] = mapped_column(String(32), nullable=False)

    versions: Mapped[list["RuleVersion"]] = relationship(
        back_populates="rule",
        # Keep historical versions even if collection sync glitches; never orphan-delete history.
        cascade="save-update, merge",
        order_by="RuleVersion.created_at",
    )


class RuleVersion(Base):
    """Immutable rule definition snapshot. Never overwrite historical rows — publish a new version."""

    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version", name="uq_rule_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("regulatory_rules.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    # {"params": {...}, "logic": "...", "description": "..."} — parameters for the rule engine
    definition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # draft | published | retired
    status: Mapped[str] = mapped_column(String(32), default="published", nullable=False, index=True)
    change_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    effective_from: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    rule: Mapped[RegulatoryRule] = relationship(back_populates="versions")
