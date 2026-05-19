"""Upgrade to version 1.6.10~rc1

Revision ID: b9c40aa70e30
Revises: c5a55e877972
Create Date: 2026-03-23 15:29:37.601495

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9c40aa70e30"
down_revision: Union[str, None] = "c5a55e877972"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")
