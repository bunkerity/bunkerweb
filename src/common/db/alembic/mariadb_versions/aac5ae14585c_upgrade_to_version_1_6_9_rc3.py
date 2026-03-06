"""Upgrade to version 1.6.9~rc3

Revision ID: aac5ae14585c
Revises: 3cc7c50485d7
Create Date: 2026-03-06 15:51:44.478590

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aac5ae14585c"
down_revision: Union[str, None] = "3cc7c50485d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc2' WHERE id = 1")
