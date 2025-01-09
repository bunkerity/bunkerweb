"""Upgrade to version 1.5.11

Revision ID: c272a8c3979c
Revises: 760f95e8bee7
Create Date: 2024-12-17 08:41:42.203308

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c272a8c3979c"
down_revision: Union[str, None] = "760f95e8bee7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'non_draft_services' column as nullable with server default
    with op.batch_alter_table("bw_metadata") as batch_op:
        batch_op.add_column(sa.Column("non_draft_services", sa.Integer(), nullable=True, server_default="0"))

    # Update existing rows
    op.execute("UPDATE bw_metadata SET non_draft_services = 0")

    # Make the column NOT NULL and drop server_default
    with op.batch_alter_table("bw_metadata") as batch_op:
        batch_op.alter_column("non_draft_services", nullable=False, server_default=None)

    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.11' WHERE id = 1")


def downgrade() -> None:
    # Drop the 'non_draft_services' column
    with op.batch_alter_table("bw_metadata") as batch_op:
        batch_op.drop_column("non_draft_services")

    # Revert version to 1.5.10
    op.execute("UPDATE bw_metadata SET version = '1.5.10' WHERE id = 1")
