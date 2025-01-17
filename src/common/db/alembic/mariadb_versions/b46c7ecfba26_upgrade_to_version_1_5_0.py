"""Upgrade to version 1.5.0

Revision ID: b46c7ecfba26
Revises:
Create Date: 2024-12-17 10:19:30.419613

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "b46c7ecfba26"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Drop 'order' column from 'bw_plugins'
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.drop_column("order")

    # Data migration: Update the version to 1.5.0
    op.execute("UPDATE bw_metadata SET version = '1.5.0' WHERE id = 1")


def downgrade() -> None:
    # Re-add the 'order' column to the 'bw_plugins' table
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.add_column(sa.Column("order", mysql.INTEGER(display_width=11), autoincrement=False, nullable=False))

    # Data migration: Update the version to 1.5.0-beta
    op.execute("UPDATE bw_metadata SET version = '1.5.0-beta' WHERE id = 1")
