"""Upgrade to version 1.6.8

Revision ID: 9fe40a1e8f4d
Revises: c1328f5f7165
Create Date: 2026-02-06 09:27:46.575191

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9fe40a1e8f4d"
down_revision: Union[str, None] = "c1328f5f7165"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc3' WHERE id = 1")
