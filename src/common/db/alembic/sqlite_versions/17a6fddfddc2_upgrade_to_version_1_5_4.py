"""Upgrade to version 1.5.4

Revision ID: 17a6fddfddc2
Revises: eb3ca0f3f20c
Create Date: 2024-12-17 08:38:06.860342

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "17a6fddfddc2"
down_revision: Union[str, None] = "eb3ca0f3f20c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create bw_ui_users table
    op.create_table(
        "bw_ui_users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=256), nullable=False, unique=True),
        sa.Column("password", sa.String(length=60), nullable=False),
    )

    # Update metadata version
    op.execute("UPDATE bw_metadata SET version = '1.5.4' WHERE id = 1")


def downgrade() -> None:
    # Drop bw_ui_users table
    op.drop_table("bw_ui_users")

    # Revert metadata version
    op.execute("UPDATE bw_metadata SET version = '1.5.3' WHERE id = 1")
