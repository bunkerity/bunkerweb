"""Upgrade to version 1.6.2-rc7

Revision ID: 6956ac2e1dd0
Revises: e1352ae8373f
Create Date: 2025-06-24 16:11:39.240525

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "6956ac2e1dd0"
down_revision: Union[str, None] = "e1352ae8373f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=mysql.ENUM("password", "text", "check", "select"),
            type_=mysql.ENUM("password", "text", "number", "check", "select", "multiselect", "multivalue"),
            existing_nullable=False,
        )

    op.add_column("bw_settings", sa.Column("separator", sa.String(length=10), nullable=True))

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc7' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_settings", "separator")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc6' WHERE id = 1")
