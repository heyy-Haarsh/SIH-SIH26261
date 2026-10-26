"""Admin configuration: rule version metadata, verified source, system settings.

Revision ID: 20261026_0005
Revises: 20261026_0004
Create Date: 2026-10-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0005"
down_revision: Union[str, None] = "20261026_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("regulatory_rules") as batch:
        batch.add_column(
            sa.Column("verified_source_ref", sa.String(length=512), nullable=False, server_default="")
        )

    with op.batch_alter_table("rule_versions") as batch:
        batch.add_column(
            sa.Column("status", sa.String(length=32), nullable=False, server_default="published")
        )
        batch.add_column(sa.Column("change_reason", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("created_by_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_rule_versions_status", ["status"])

    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key", sa.String(length=96), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")
    with op.batch_alter_table("rule_versions") as batch:
        batch.drop_index("ix_rule_versions_status")
        batch.drop_column("published_at")
        batch.drop_column("effective_to")
        batch.drop_column("created_by_id")
        batch.drop_column("change_reason")
        batch.drop_column("status")
    with op.batch_alter_table("regulatory_rules") as batch:
        batch.drop_column("verified_source_ref")
