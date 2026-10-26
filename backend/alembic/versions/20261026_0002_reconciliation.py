"""Add reconciliation_runs, reconciliation_items, reconciliation_values.

Revision ID: 20261026_0002
Revises: 20261026_0001
Create Date: 2026-10-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0002"
down_revision: Union[str, None] = "20261026_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "application_id",
            sa.String(length=36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "validation_run_id",
            sa.String(length=36),
            sa.ForeignKey("validation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False, server_default="validation"),
        sa.Column("triggered_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recon_runs_app_created", "reconciliation_runs", ["application_id", "created_at"])
    op.create_index(
        "ix_reconciliation_runs_application_id", "reconciliation_runs", ["application_id"]
    )
    op.create_index(
        "ix_reconciliation_runs_input_fingerprint", "reconciliation_runs", ["input_fingerprint"]
    )

    op.create_table(
        "reconciliation_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.String(length=36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("original_outcome", sa.String(length=32), nullable=False),
        sa.Column("match_kind", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recon_items_app_field", "reconciliation_items", ["application_id", "field_name"])
    op.create_index("ix_recon_items_app_fp", "reconciliation_items", ["application_id", "fingerprint"])
    op.create_index("ix_reconciliation_items_run_id", "reconciliation_items", ["run_id"])
    op.create_index("ix_reconciliation_items_application_id", "reconciliation_items", ["application_id"])
    op.create_index("ix_reconciliation_items_outcome", "reconciliation_items", ["outcome"])
    op.create_index("ix_reconciliation_items_status", "reconciliation_items", ["status"])

    op.create_table(
        "reconciliation_values",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "item_id",
            sa.String(length=36),
            sa.ForeignKey("reconciliation_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column(
            "extracted_field_id",
            sa.String(length=36),
            sa.ForeignKey("extracted_fields.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("page_reference", sa.String(length=64), nullable=True),
        sa.Column("evidence_snippet", sa.Text(), nullable=True),
    )
    op.create_index("ix_reconciliation_values_item_id", "reconciliation_values", ["item_id"])
    op.create_index("ix_reconciliation_values_document_id", "reconciliation_values", ["document_id"])


def downgrade() -> None:
    op.drop_table("reconciliation_values")
    op.drop_table("reconciliation_items")
    op.drop_table("reconciliation_runs")
