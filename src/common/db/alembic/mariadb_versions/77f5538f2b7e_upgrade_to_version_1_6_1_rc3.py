"""Upgrade to version 1.6.1-rc3

Revision ID: 77f5538f2b7e
Revises: b2c34a5c2c67
Create Date: 2025-03-03 15:07:50.169265

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "77f5538f2b7e"
down_revision: Union[str, None] = "b2c34a5c2c67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bw_ui_user_columns_preferences") as batch_op:
        batch_op.alter_column(
            "table_name",
            existing_type=mysql.ENUM("bans", "configs", "instances", "jobs", "plugins", "reports", "services"),
            type_=sa.String(length=256),
            existing_nullable=False,
        )

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc3' WHERE id = 1")


def downgrade() -> None:
    with op.batch_alter_table("bw_ui_user_columns_preferences") as batch_op:
        batch_op.alter_column(
            "table_name",
            existing_type=sa.String(length=256),
            type_=mysql.ENUM("bans", "configs", "instances", "jobs", "plugins", "reports", "services"),
            existing_nullable=False,
        )

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc2' WHERE id = 1")
