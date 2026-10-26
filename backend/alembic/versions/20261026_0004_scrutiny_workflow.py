"""Add scrutiny workflow score/summary columns and deficiency response fields.

Revision ID: 20261026_0004
Revises: 20261026_0003
Create Date: 2026-10-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0004"
down_revision: Union[str, None] = "20261026_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("score_config_version", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("score_breakdown", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("scrutiny_summary", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(
            sa.Column("deficiency_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_transition_note", sa.Text(), nullable=True))

    with op.batch_alter_table("deficiency_notices") as batch:
        batch.add_column(sa.Column("applicant_response", sa.Text(), nullable=True))
        batch.add_column(sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("deficiency_notices") as batch:
        batch.drop_column("responded_at")
        batch.drop_column("applicant_response")
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("last_transition_note")
        batch.drop_column("last_transition_at")
        batch.drop_column("deficiency_count")
        batch.drop_column("scrutiny_summary")
        batch.drop_column("score_breakdown")
        batch.drop_column("score_config_version")
