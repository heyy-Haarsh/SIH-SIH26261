"""Capture the institution name on each application.

Revision ID: 20261028_0008
Revises: 20261027_0007
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_0008"
down_revision: Union[str, None] = "20261027_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(
            sa.Column("institution_name", sa.String(length=255), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("institution_name")
