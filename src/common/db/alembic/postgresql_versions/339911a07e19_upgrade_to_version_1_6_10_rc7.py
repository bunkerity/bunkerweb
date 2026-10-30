"""Upgrade to version 1.6.10~rc7

Revision ID: 339911a07e19
Revises: 25255ccae247
Create Date: 2026-05-13 11:53:36.799878

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "339911a07e19"
down_revision: Union[str, None] = "25255ccae247"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc7' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc6' WHERE id = 1")
