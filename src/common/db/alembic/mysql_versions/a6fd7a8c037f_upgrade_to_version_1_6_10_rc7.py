"""Upgrade to version 1.6.10~rc7

Revision ID: a6fd7a8c037f
Revises: 75253944b270
Create Date: 2026-05-13 11:52:43.586659

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6fd7a8c037f"
down_revision: Union[str, None] = "75253944b270"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc7' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc6' WHERE id = 1")
