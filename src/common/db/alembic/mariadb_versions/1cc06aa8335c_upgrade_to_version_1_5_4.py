"""Upgrade to version 1.5.4

Revision ID: 1cc06aa8335c
Revises: c38183e63472
Create Date: 2024-12-17 10:19:48.503973

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "1cc06aa8335c"
down_revision: Union[str, None] = "c38183e63472"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new table 'bw_ui_users'
    op.create_table(
        "bw_ui_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=256), nullable=False),
        sa.Column("password", sa.String(length=60), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    # Update metadata version
    op.execute("UPDATE bw_metadata SET version = '1.5.4' WHERE id = 1")


def downgrade() -> None:
    # Drop the table 'bw_ui_users'
    op.drop_table("bw_ui_users")

    # Revert metadata version
    op.execute("UPDATE bw_metadata SET version = '1.5.3' WHERE id = 1")
