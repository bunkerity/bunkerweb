"""Upgrade to version 1.5.11

Revision ID: 12ffcd2b9d63
Revises: b03a64d4d34a
Create Date: 2024-12-19 13:30:48.808893

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "12ffcd2b9d63"
down_revision: Union[str, None] = "b03a64d4d34a"
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
