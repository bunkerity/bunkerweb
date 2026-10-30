"""Upgrade to version 1.6.17~rc2

Revision ID: f4eacc8348f6
Revises: fd7d5270fa73
Create Date: 2026-10-16 15:22:33.673089

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4eacc8348f6"
down_revision: Union[str, None] = "fd7d5270fa73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.17~rc2' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.17~rc1' WHERE id = 1")
