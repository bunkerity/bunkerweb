"""Upgrade to version 1.6.10~rc1

Revision ID: 8ae1d2f15d0c
Revises: d7578fb6ec98
Create Date: 2026-03-23 15:31:04.340566

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8ae1d2f15d0c"
down_revision: Union[str, None] = "d7578fb6ec98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")
