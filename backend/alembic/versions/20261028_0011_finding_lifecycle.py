"""Finding lifecycle history and multi-finding clarification links.

The ``findings.status`` column is a non-native VARCHAR(32), so the new lifecycle values
(under_review, clarification_requested, superseded, reopened) need no column change.

Revision ID: 20261028_0011
Revises: 20261028_0010
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_0011"
down_revision: Union[str, None] = "20261028_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "finding_transitions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "finding_id", sa.String(length=36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "application_id",
            sa.String(length=36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("actor_name", sa.String(length=128), nullable=False, server_default="system"),
        sa.Column("actor_role", sa.String(length=32), nullable=False, server_default="system"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_finding_transitions_finding_id", "finding_transitions", ["finding_id"])
    op.create_index("ix_finding_transitions_application_id", "finding_transitions", ["application_id"])
    op.create_index("ix_finding_transitions_created_at", "finding_transitions", ["created_at"])

    op.create_table(
        "deficiency_findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "deficiency_id",
            sa.String(length=36),
            sa.ForeignKey("deficiency_notices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "finding_id", sa.String(length=36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deficiency_findings_deficiency_id", "deficiency_findings", ["deficiency_id"])
    op.create_index("ix_deficiency_findings_finding_id", "deficiency_findings", ["finding_id"])

    # Backfill: existing single-finding clarifications keep their link.
    op.execute(
        "INSERT INTO deficiency_findings (id, deficiency_id, finding_id, created_at) "
        "SELECT lower(hex(randomblob(16))), id, finding_id, created_at "
        "FROM deficiency_notices WHERE finding_id IS NOT NULL"
        if op.get_bind().dialect.name == "sqlite"
        else "INSERT INTO deficiency_findings (id, deficiency_id, finding_id, created_at) "
        "SELECT replace(gen_random_uuid()::text, '-', ''), id, finding_id, created_at "
        "FROM deficiency_notices WHERE finding_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_deficiency_findings_finding_id", table_name="deficiency_findings")
    op.drop_index("ix_deficiency_findings_deficiency_id", table_name="deficiency_findings")
    op.drop_table("deficiency_findings")
    op.drop_index("ix_finding_transitions_created_at", table_name="finding_transitions")
    op.drop_index("ix_finding_transitions_application_id", table_name="finding_transitions")
    op.drop_index("ix_finding_transitions_finding_id", table_name="finding_transitions")
    op.drop_table("finding_transitions")
