"""Upgrade to version 1.6.8~rc2

Revision ID: 002e685396c1
Revises: 46312f0c8948
Create Date: 2026-01-23 16:36:41.126206

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002e685396c1"
down_revision: Union[str, None] = "46312f0c8948"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc1' WHERE id = 1")
