"""Upgrade to version 1.6.6-rc3

Revision ID: 9dc610f067ed
Revises: 9f96ae876cdf
Create Date: 2025-11-17 17:17:44.991325

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9dc610f067ed"
down_revision: Union[str, None] = "9f96ae876cdf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc2' WHERE id = 1")
