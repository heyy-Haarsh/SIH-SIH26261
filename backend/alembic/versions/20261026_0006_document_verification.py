"""Phase 7 three-layer document verification tables and status columns.

Revision ID: 20261026_0006
Revises: 20261026_0005
Create Date: 2026-10-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0006"
down_revision: Union[str, None] = "20261026_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "rule_validation_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending",
            )
        )
        batch.add_column(
            sa.Column(
                "external_verification_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending",
            )
        )
        batch.add_column(
            sa.Column(
                "review_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending",
            )
        )
        batch.add_column(sa.Column("latest_verification_run_id", sa.String(length=36), nullable=True))

    op.create_table(
        "document_verification_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("application_id", sa.String(length=36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("validation_run_id", sa.String(length=36), sa.ForeignKey("validation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("config_code", sa.String(length=64), nullable=False),
        sa.Column("config_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rule_validation_status", sa.String(length=32), nullable=False),
        sa.Column("external_verification_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("scrutiny_report", sa.JSON(), nullable=False),
        sa.Column("triggered_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_docverif_run_app", "document_verification_runs", ["application_id", "created_at"])
    op.create_index("ix_docverif_run_doc", "document_verification_runs", ["document_id", "created_at"])

    op.create_table(
        "document_verification_checks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("document_verification_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.String(length=36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("check_code", sa.String(length=96), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("adapter", sa.String(length=64), nullable=False),
        sa.Column("is_synthetic_rule", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_docverif_check_run_layer", "document_verification_checks", ["run_id", "layer"])


def downgrade() -> None:
    op.drop_index("ix_docverif_check_run_layer", table_name="document_verification_checks")
    op.drop_table("document_verification_checks")
    op.drop_index("ix_docverif_run_doc", table_name="document_verification_runs")
    op.drop_index("ix_docverif_run_app", table_name="document_verification_runs")
    op.drop_table("document_verification_runs")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("latest_verification_run_id")
        batch.drop_column("review_status")
        batch.drop_column("external_verification_status")
        batch.drop_column("rule_validation_status")
