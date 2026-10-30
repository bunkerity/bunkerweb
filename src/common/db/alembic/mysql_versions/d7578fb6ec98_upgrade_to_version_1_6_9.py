"""Upgrade to version 1.6.9

Revision ID: d7578fb6ec98
Revises: 4dc4e52dcc50
Create Date: 2026-03-13 16:44:41.931672

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7578fb6ec98"
down_revision: Union[str, None] = "4dc4e52dcc50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")
