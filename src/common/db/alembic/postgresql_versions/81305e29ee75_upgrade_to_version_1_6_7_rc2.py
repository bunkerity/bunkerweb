"""Upgrade to version 1.6.7~rc2

Revision ID: 81305e29ee75
Revises: 946db7041f86
Create Date: 2026-01-06 17:04:36.024195

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81305e29ee75"
down_revision: Union[str, None] = "946db7041f86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc1' WHERE id = 1")
