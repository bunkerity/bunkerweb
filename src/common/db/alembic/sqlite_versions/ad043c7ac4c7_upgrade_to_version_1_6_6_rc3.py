"""Upgrade to version 1.6.6-rc3

Revision ID: ad043c7ac4c7
Revises: 5c2ab7aee214
Create Date: 2025-11-17 17:04:07.228543

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ad043c7ac4c7"
down_revision: Union[str, None] = "5c2ab7aee214"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc2' WHERE id = 1")
