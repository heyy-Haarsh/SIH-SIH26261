"""Category-scoped configuration: requirements, rules, published versions, check results.

Revision ID: 20261029_0013
Revises: 20261028_0012
Create Date: 2026-10-29

Schema only. Existing categories keep working unchanged: on application start
``category_config_service.ensure_baseline`` (idempotent) creates a requirement row for every entry
of each category's existing checklist, publishes configuration version 1 from it, pins existing
applications to that version, and links existing documents to their requirement id. No existing
row is deleted or rewritten, and ``application_categories.required_documents`` is kept.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0013"
down_revision: Union[str, None] = "20261028_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = lambda: sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)  # noqa: E731


def upgrade() -> None:
    op.add_column(
        "application_categories",
        sa.Column("info_fields", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.create_table(
        "document_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("application_categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("document_type_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allowed_types", sa.JSON(), nullable=False),
        sa.Column("max_size_mb", sa.Integer(), nullable=True),
        sa.Column("expected_fields", sa.JSON(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _TS(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("category_id", "code", name="uq_docreq_category_code"),
    )
    op.create_index("ix_document_requirements_category_id", "document_requirements", ["category_id"])
    op.create_index("ix_docreq_category_active", "document_requirements", ["category_id", "is_active"])

    op.create_table(
        "requirement_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("application_categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.String(36), sa.ForeignKey("document_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("rule_type", sa.String(48), nullable=False, server_default="unstructured"),
        sa.Column("source_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        _TS(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("requirement_id", "code", name="uq_reqrule_requirement_code"),
    )
    op.create_index("ix_requirement_rules_requirement_id", "requirement_rules", ["requirement_id"])
    op.create_index("ix_reqrule_category", "requirement_rules", ["category_id"])

    op.create_table(
        "requirement_rule_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("requirement_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("authoring_mode", sa.String(8), nullable=False, server_default="json"),
        sa.Column("natural_language", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        _TS(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rule_id", "version", name="uq_reqrulever_rule_version"),
    )
    op.create_index("ix_requirement_rule_versions_rule_id", "requirement_rule_versions", ["rule_id"])
    op.create_index("ix_requirement_rule_versions_status", "requirement_rule_versions", ["status"])

    op.create_table(
        "category_config_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("application_categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("category_id", "version", name="uq_catconfig_category_version"),
    )
    op.create_index("ix_category_config_versions_category_id", "category_config_versions", ["category_id"])

    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("config_version_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("info_values", sa.JSON(), nullable=False, server_default="{}"))
        batch.create_foreign_key(
            "fk_applications_config_version", "category_config_versions", ["config_version_id"], ["id"]
        )
        batch.create_index("ix_applications_config_version_id", ["config_version_id"])

    op.add_column("documents", sa.Column("requirement_id", sa.String(36), nullable=True))
    op.create_index("ix_documents_requirement_id", "documents", ["requirement_id"])

    op.create_table(
        "rule_check_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_version", sa.Integer(), nullable=True),
        sa.Column("requirement_id", sa.String(36), nullable=False),
        sa.Column("requirement_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("rule_id", sa.String(36), nullable=False),
        sa.Column("rule_version_id", sa.String(36), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("rule_title", sa.String(255), nullable=False, server_default=""),
        sa.Column("config_version_id", sa.String(36), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("validation_run_id", sa.String(36), nullable=True),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        _TS(),
    )
    op.create_index("ix_rule_check_results_document_id", "rule_check_results", ["document_id"])
    op.create_index("ix_rulecheck_app_current", "rule_check_results", ["application_id", "is_current"])


def downgrade() -> None:
    op.drop_index("ix_rulecheck_app_current", table_name="rule_check_results")
    op.drop_index("ix_rule_check_results_document_id", table_name="rule_check_results")
    op.drop_table("rule_check_results")
    op.drop_index("ix_documents_requirement_id", table_name="documents")
    op.drop_column("documents", "requirement_id")
    with op.batch_alter_table("applications") as batch:
        batch.drop_index("ix_applications_config_version_id")
        batch.drop_constraint("fk_applications_config_version", type_="foreignkey")
        batch.drop_column("info_values")
        batch.drop_column("config_version_id")
    op.drop_index("ix_category_config_versions_category_id", table_name="category_config_versions")
    op.drop_table("category_config_versions")
    op.drop_index("ix_requirement_rule_versions_status", table_name="requirement_rule_versions")
    op.drop_index("ix_requirement_rule_versions_rule_id", table_name="requirement_rule_versions")
    op.drop_table("requirement_rule_versions")
    op.drop_index("ix_reqrule_category", table_name="requirement_rules")
    op.drop_index("ix_requirement_rules_requirement_id", table_name="requirement_rules")
    op.drop_table("requirement_rules")
    op.drop_index("ix_docreq_category_active", table_name="document_requirements")
    op.drop_index("ix_document_requirements_category_id", table_name="document_requirements")
    op.drop_table("document_requirements")
    op.drop_column("application_categories", "info_fields")
