"""Upgrade to version 1.5.11

Revision ID: efb577b1c25d
Revises: 0a2e336b02e7
Create Date: 2024-12-19 14:42:50.054087

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "efb577b1c25d"
down_revision: Union[str, None] = "0a2e336b02e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new non_draft_services column to bw_metadata
    op.add_column("bw_metadata", sa.Column("non_draft_services", sa.Integer(), nullable=False, server_default="0"))

    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.11' WHERE id = 1")


def downgrade() -> None:
    # Reverse the addition of the non_draft_services column
    op.drop_column("bw_metadata", "non_draft_services")

    # Revert version to 1.5.10
    op.execute("UPDATE bw_metadata SET version = '1.5.10' WHERE id = 1")
