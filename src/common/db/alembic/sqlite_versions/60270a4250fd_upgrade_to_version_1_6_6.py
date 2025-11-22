"""Upgrade to version 1.6.6

Revision ID: 60270a4250fd
Revises: ad043c7ac4c7
Create Date: 2025-11-21 19:06:04.700814

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "60270a4250fd"
down_revision: Union[str, None] = "ad043c7ac4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc3' WHERE id = 1")
