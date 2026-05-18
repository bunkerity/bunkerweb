"""Upgrade to version 1.6.8~rc3

Revision ID: c9c2b1bb33d6
Revises: f9ec52459ddb
Create Date: 2026-01-30 12:36:25.841389

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9c2b1bb33d6"
down_revision: Union[str, None] = "f9ec52459ddb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc2' WHERE id = 1")
