"""Upgrade to version 1.6.7

Revision ID: 1e3b377594f6
Revises: 81305e29ee75
Create Date: 2026-01-09 14:46:09.189425

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1e3b377594f6"
down_revision: Union[str, None] = "81305e29ee75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.6.7' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata' back to 1.6.7~rc2
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc2' WHERE id = 1")
