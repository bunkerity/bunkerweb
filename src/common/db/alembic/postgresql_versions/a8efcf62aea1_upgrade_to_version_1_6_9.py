"""Upgrade to version 1.6.9

Revision ID: a8efcf62aea1
Revises: 9cd5363ac925
Create Date: 2026-03-13 16:46:16.030018

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8efcf62aea1"
down_revision: Union[str, None] = "9cd5363ac925"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")
