"""Upgrade to version 1.6.9~rc4

Revision ID: c3114f5051a8
Revises: 20cfd1a35c0e
Create Date: 2026-03-10 08:10:33.664321

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3114f5051a8"
down_revision: Union[str, None] = "20cfd1a35c0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")
