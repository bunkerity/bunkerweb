"""Upgrade to version 1.6.9~rc1

Revision ID: 7ff687d13019
Revises: 9fe40a1e8f4d
Create Date: 2026-02-13 20:08:10.891681

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ff687d13019"
down_revision: Union[str, None] = "9fe40a1e8f4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8' WHERE id = 1")
