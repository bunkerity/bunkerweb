"""Upgrade to version 1.6.9

Revision ID: c5a55e877972
Revises: c3114f5051a8
Create Date: 2026-03-13 16:38:24.613334

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c5a55e877972"
down_revision: Union[str, None] = "c3114f5051a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")
