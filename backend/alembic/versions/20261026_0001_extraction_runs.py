"""Add extraction_runs and expand extracted_fields provenance.

Revision ID: 20261026_0001
Revises:
Create Date: 2026-10-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_version_id", sa.String(length=36), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.String(length=36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("validation_run_id", sa.String(length=36), sa.ForeignKey("validation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_kind", sa.String(length=32), nullable=False),
        sa.Column("selected_category", sa.String(length=64), nullable=True),
        sa.Column("predicted_category", sa.String(length=32), nullable=False),
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("category_method", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("category_signals", sa.JSON(), nullable=False),
        sa.Column("category_mismatch", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("pages_with_text", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages_ocr", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stage_timings_ms", sa.JSON(), nullable=False),
        sa.Column("ocr_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ocr_languages", sa.String(length=64), nullable=False, server_default="eng"),
        sa.Column("triggered_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "document_version_id",
            "content_sha256",
            "config_fingerprint",
            name="uq_extraction_idempotent",
        ),
    )
    op.create_index("ix_extraction_runs_docver_created", "extraction_runs", ["document_version_id", "created_at"])

    with op.batch_alter_table("extracted_fields") as batch:
        batch.add_column(sa.Column("extraction_run_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("raw_value", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("normalized_value", sa.Text(), nullable=True))
        batch.add_column(sa.Column("ocr_confidence", sa.Float(), nullable=True))
        batch.add_column(sa.Column("page_number", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("bbox_x0", sa.Float(), nullable=True))
        batch.add_column(sa.Column("bbox_y0", sa.Float(), nullable=True))
        batch.add_column(sa.Column("bbox_x1", sa.Float(), nullable=True))
        batch.add_column(sa.Column("bbox_y1", sa.Float(), nullable=True))
        batch.add_column(sa.Column("coordinate_space", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending"))
        batch.add_column(sa.Column("is_conflict", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("candidate_values", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("unit", sa.String(length=32), nullable=True))
        batch.create_foreign_key(
            "fk_extracted_fields_extraction_run",
            "extraction_runs",
            ["extraction_run_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_extracted_fields_run_name", ["extraction_run_id", "field_name"])

    with op.batch_alter_table("findings") as batch:
        batch.add_column(sa.Column("extraction_run_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_findings_extraction_run",
            "extraction_runs",
            ["extraction_run_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("findings") as batch:
        batch.drop_constraint("fk_findings_extraction_run", type_="foreignkey")
        batch.drop_column("extraction_run_id")
    with op.batch_alter_table("extracted_fields") as batch:
        batch.drop_index("ix_extracted_fields_run_name")
        batch.drop_constraint("fk_extracted_fields_extraction_run", type_="foreignkey")
        for col in (
            "extraction_run_id",
            "raw_value",
            "normalized_value",
            "ocr_confidence",
            "page_number",
            "bbox_x0",
            "bbox_y0",
            "bbox_x1",
            "bbox_y1",
            "coordinate_space",
            "review_status",
            "is_conflict",
            "candidate_values",
            "unit",
        ):
            batch.drop_column(col)
    op.drop_index("ix_extraction_runs_docver_created", table_name="extraction_runs")
    op.drop_table("extraction_runs")
