"""Upgrade to version 1.6.6-rc2

Revision ID: 9f96ae876cdf
Revises: 34aa2cfacc8d
Create Date: 2025-11-05 14:34:32.561884

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f96ae876cdf"
down_revision: Union[str, None] = "34aa2cfacc8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc1' WHERE id = 1")
