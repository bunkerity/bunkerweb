"""Upgrade to version 1.5.0

Revision ID: 8bb3be426524
Revises:
Create Date: 2024-12-17 08:35:24.898488

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8bb3be426524"
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
    # Step 1: Add 'order' column back to 'bw_plugins' (with a default value of 0 for NOT NULL constraint)
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.add_column(sa.Column("order", sa.Integer(), nullable=True, server_default="0"))

    # Step 2: Set default value for existing rows
    op.execute("UPDATE bw_plugins SET `order` = 0")

    # Step 3: Alter 'order' column to NOT NULL
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.alter_column("order", nullable=False)

    # Data migration: Update the version to 1.5.0-beta
    op.execute("UPDATE bw_metadata SET version = '1.5.0-beta' WHERE id = 1")
