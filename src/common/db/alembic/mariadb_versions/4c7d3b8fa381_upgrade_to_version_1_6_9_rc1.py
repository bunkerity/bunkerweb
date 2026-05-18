"""Upgrade to version 1.6.9~rc1

Revision ID: 4c7d3b8fa381
Revises: 8bfd4261a1a8
Create Date: 2026-02-13 19:49:58.540474

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c7d3b8fa381"
down_revision: Union[str, None] = "8bfd4261a1a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8' WHERE id = 1")
