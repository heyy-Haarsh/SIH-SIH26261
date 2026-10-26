"""Add forensics_runs, forensics_indicators, forensics_evidence.

Revision ID: 20261026_0003
Revises: 20261026_0002
Create Date: 2026-10-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0003"
down_revision: Union[str, None] = "20261026_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forensics_runs",
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
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_forensics_runs_app_created", "forensics_runs", ["application_id", "created_at"])
    op.create_index("ix_forensics_runs_application_id", "forensics_runs", ["application_id"])
    op.create_index("ix_forensics_runs_input_fingerprint", "forensics_runs", ["input_fingerprint"])

    op.create_table(
        "forensics_indicators",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("forensics_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.String(length=36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("original_risk_class", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_pages", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("indicator_metadata", sa.JSON(), nullable=False),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forensics_ind_app_code", "forensics_indicators", ["application_id", "code"])
    op.create_index("ix_forensics_ind_app_fp", "forensics_indicators", ["application_id", "fingerprint"])
    op.create_index("ix_forensics_indicators_run_id", "forensics_indicators", ["run_id"])
    op.create_index("ix_forensics_indicators_application_id", "forensics_indicators", ["application_id"])
    op.create_index("ix_forensics_indicators_document_id", "forensics_indicators", ["document_id"])
    op.create_index("ix_forensics_indicators_code", "forensics_indicators", ["code"])
    op.create_index("ix_forensics_indicators_risk_class", "forensics_indicators", ["risk_class"])
    op.create_index("ix_forensics_indicators_status", "forensics_indicators", ["status"])

    op.create_table(
        "forensics_evidence",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "indicator_id",
            sa.String(length=36),
            sa.ForeignKey("forensics_indicators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_name", sa.String(length=255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("page_reference", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forensics_evidence_indicator_id", "forensics_evidence", ["indicator_id"])


def downgrade() -> None:
    op.drop_table("forensics_evidence")
    op.drop_table("forensics_indicators")
    op.drop_table("forensics_runs")
