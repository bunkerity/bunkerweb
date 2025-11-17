"""Upgrade to version 1.6.6-rc3

Revision ID: be495eb745b1
Revises: 2ff5393bbaca
Create Date: 2025-11-17 17:08:02.676391

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "be495eb745b1"
down_revision: Union[str, None] = "2ff5393bbaca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc2' WHERE id = 1")
