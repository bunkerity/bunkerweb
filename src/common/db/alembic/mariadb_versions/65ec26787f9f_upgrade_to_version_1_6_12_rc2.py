"""Upgrade to version 1.6.12~rc2

Revision ID: 65ec26787f9f
Revises: b0310ce7edd8
Create Date: 2026-06-16 07:34:32.359952

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65ec26787f9f"
down_revision: Union[str, None] = "b0310ce7edd8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc2' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc1' WHERE id = 1")
