"""Upgrade to version 1.6.2-rc3

Revision ID: 111bd3f822da
Revises: 32500d8cf3b0
Create Date: 2025-06-06 08:32:41.372293

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "111bd3f822da"
down_revision: Union[str, None] = "32500d8cf3b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc2' WHERE id = 1")
