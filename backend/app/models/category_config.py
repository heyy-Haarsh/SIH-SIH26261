"""Category-scoped configuration: document requirements, rules, published versions, check results.

Relationships (all by stable id, never by display name)::

    ApplicationCategory 1─* DocumentRequirement 1─* RequirementRule 1─* RequirementRuleVersion
    ApplicationCategory 1─* CategoryConfigVersion          (immutable published snapshots)
    Application ──pins──▶ CategoryConfigVersion            (the configuration it is judged by)
    Document ──▶ DocumentRequirement (requirement_id)       (the exact requirement it answers)
    RuleCheckResult ──▶ rule version + document version + config version + application

A rule belongs to ONE requirement of ONE category, so the same document type required by two
categories has two independent requirement rows and two independent rule sets.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UTCDateTime, new_id, utcnow


class DocumentRequirement(Base, TimestampMixin):
    __tablename__ = "document_requirements"
    __table_args__ = (
        UniqueConstraint("category_id", "code", name="uq_docreq_category_code"),
        Index("ix_docreq_category_active", "category_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category_id: Mapped[str] = mapped_column(
        ForeignKey("application_categories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Stable within the category; this is what Document.requirement_code stores.
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    # Reusable document type (e.g. the verification config code). Defaults to ``code``.
    document_type_code: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allowed_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    max_size_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Extracted fields this requirement is expected to supply (informational / rule authoring aid).
    expected_fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Deactivated rather than deleted so applications that reference it keep their history.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rules: Mapped[list["RequirementRule"]] = relationship(
        back_populates="requirement", cascade="save-update, merge", order_by="RequirementRule.created_at"
    )


class RequirementRule(Base, TimestampMixin):
    __tablename__ = "requirement_rules"
    __table_args__ = (
        UniqueConstraint("requirement_id", "code", name="uq_reqrule_requirement_code"),
        Index("ix_reqrule_category", "category_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Denormalised from the requirement so a rule can never be queried outside its category.
    category_id: Mapped[str] = mapped_column(
        ForeignKey("application_categories.id", ondelete="CASCADE"), nullable=False
    )
    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("document_requirements.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # The check type of the latest version (synced on save); "unstructured" until a definition exists.
    rule_type: Mapped[str] = mapped_column(String(48), default="unstructured", nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)

    requirement: Mapped[DocumentRequirement] = relationship(back_populates="rules")
    versions: Mapped[list["RequirementRuleVersion"]] = relationship(
        back_populates="rule", cascade="save-update, merge", order_by="RequirementRuleVersion.version"
    )


class RequirementRuleVersion(Base):
    """Immutable once published. Editing creates a new draft version."""

    __tablename__ = "requirement_rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version", name="uq_reqrulever_rule_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("requirement_rules.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # draft | published | retired
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False, index=True)
    # plain | json — how the administrator authored it. Plain text is never executed.
    authoring_mode: Mapped[str] = mapped_column(String(8), default="json", nullable=False)
    natural_language: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Metadata is versioned with the definition so a published version never changes meaning.
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Result of the last validation: {valid, errors, warnings, unsupported, requiresSource, requiredInputs}
    validation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)

    rule: Mapped[RequirementRule] = relationship(back_populates="versions")


class CategoryConfigVersion(Base):
    """An immutable, published snapshot of a category's configuration.

    Lifecycle: the editable working copy (draft) lives in the live tables; publishing validates
    it and writes a new snapshot here (``published``). The previous one becomes ``superseded`` but
    is kept, because applications and results point at it.
    """

    __tablename__ = "category_config_versions"
    __table_args__ = (UniqueConstraint("category_id", "version", name="uq_catconfig_category_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category_id: Mapped[str] = mapped_column(
        ForeignKey("application_categories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="published", nullable=False)  # published|superseded
    # {"info_fields": [...], "requirements": [{..., "rules": [{...definition...}]}]}
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_by_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class RuleCheckResult(Base):
    """One evaluation of one rule version against one document version."""

    __tablename__ = "rule_check_results"
    __table_args__ = (Index("ix_rulecheck_app_current", "application_id", "is_current"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=True
    )
    document_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requirement_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requirement_code: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    rule_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rule_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    rule_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    config_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # passed | failed | unable_to_evaluate | pending | source_unavailable | manual_review
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="warning", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # False once a newer run (or a newer document version) has replaced this result.
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
