"""Upgrade to version 1.6.10~rc2

Revision ID: d2bb8a70b034
Revises: 8ae1d2f15d0c
Create Date: 2026-03-27 18:13:58.570021

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2bb8a70b034"
down_revision: Union[str, None] = "8ae1d2f15d0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc1' WHERE id = 1")
