"""Upgrade to version 1.6.6

Revision ID: 8a140aff73dd
Revises: be495eb745b1
Create Date: 2025-11-22 12:39:47.147262

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a140aff73dd"
down_revision: Union[str, None] = "be495eb745b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc3' WHERE id = 1")
