"""Upgrade to version 1.6.10~rc5

Revision ID: fb7e9af64d1d
Revises: 81a4439e7193
Create Date: 2026-05-04 16:00:18.554923

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb7e9af64d1d"
down_revision: Union[str, None] = "81a4439e7193"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc5' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")
