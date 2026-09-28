"""Upgrade to version 1.6.10~rc1

Revision ID: 74557875b1f5
Revises: a8efcf62aea1
Create Date: 2026-03-23 16:16:44.561114

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "74557875b1f5"
down_revision: Union[str, None] = "a8efcf62aea1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")
