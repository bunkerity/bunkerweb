"""Upgrade to version 1.6.10~rc5

Revision ID: 4a16ae77a27b
Revises: 7975fc12c5ca
Create Date: 2026-05-04 15:58:17.224841

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a16ae77a27b"
down_revision: Union[str, None] = "7975fc12c5ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc5' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")
