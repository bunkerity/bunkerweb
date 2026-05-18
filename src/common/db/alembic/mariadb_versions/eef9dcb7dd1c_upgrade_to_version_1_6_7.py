"""Upgrade to version 1.6.7

Revision ID: eef9dcb7dd1c
Revises: 9fd808d31d16
Create Date: 2026-01-09 14:40:13.853279

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eef9dcb7dd1c"
down_revision: Union[str, None] = "9fd808d31d16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.6.7' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata' back to 1.6.7~rc2
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc2' WHERE id = 1")
