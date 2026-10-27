"""Hash-chained audit log table.

Revision ID: 20261027_0007
Revises: 20261026_0006
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0007"
down_revision: Union[str, None] = "20261026_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_chain_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("rule_version", sa.String(length=64), nullable=True),
        sa.Column("connector_used", sa.String(length=96), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("sequence"),
    )
    op.create_index("ix_audit_chain_events_sequence", "audit_chain_events", ["sequence"])


def downgrade() -> None:
    op.drop_index("ix_audit_chain_events_sequence", table_name="audit_chain_events")
    op.drop_table("audit_chain_events")
