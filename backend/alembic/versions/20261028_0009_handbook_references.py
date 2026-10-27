"""Verified AICTE handbook reference registry.

Revision ID: 20261028_0009
Revises: 20261028_0008
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_0009"
down_revision: Union[str, None] = "20261028_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "handbook_references",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("reference_key", sa.String(length=128), nullable=False),
        sa.Column("edition", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("section", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("page", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_handbook_references_reference_key", "handbook_references", ["reference_key"], unique=True
    )
    with op.batch_alter_table("findings") as batch:
        batch.add_column(
            sa.Column("fingerprint", sa.String(length=64), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("findings") as batch:
        batch.drop_column("fingerprint")
    op.drop_index("ix_handbook_references_reference_key", table_name="handbook_references")
    op.drop_table("handbook_references")
