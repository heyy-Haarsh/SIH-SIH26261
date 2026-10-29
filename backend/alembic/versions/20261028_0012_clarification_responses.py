"""Clarification response history and replacement-required flag.

Revision ID: 20261028_0012
Revises: 20261028_0011
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_0012"
down_revision: Union[str, None] = "20261028_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deficiency_notices",
        sa.Column("requires_replacement", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "deficiency_responses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "deficiency_id",
            sa.String(length=36),
            sa.ForeignKey("deficiency_notices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("documents", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deficiency_responses_deficiency_id", "deficiency_responses", ["deficiency_id"])

    # Responses given before this migration keep their text as the first history entry.
    op.execute(
        "INSERT INTO deficiency_responses (id, deficiency_id, mode, text, documents, created_at) "
        "SELECT lower(hex(randomblob(16))), id, 'text', applicant_response, '[]', "
        "COALESCE(responded_at, created_at) "
        "FROM deficiency_notices WHERE applicant_response IS NOT NULL AND applicant_response <> ''"
        if op.get_bind().dialect.name == "sqlite"
        else "INSERT INTO deficiency_responses (id, deficiency_id, mode, text, documents, created_at) "
        "SELECT replace(gen_random_uuid()::text, '-', ''), id, 'text', applicant_response, '[]', "
        "COALESCE(responded_at, created_at) "
        "FROM deficiency_notices WHERE applicant_response IS NOT NULL AND applicant_response <> ''"
    )


def downgrade() -> None:
    op.drop_index("ix_deficiency_responses_deficiency_id", table_name="deficiency_responses")
    op.drop_table("deficiency_responses")
    op.drop_column("deficiency_notices", "requires_replacement")
