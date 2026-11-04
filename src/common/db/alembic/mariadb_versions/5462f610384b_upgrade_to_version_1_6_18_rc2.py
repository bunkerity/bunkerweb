"""Upgrade to version 1.6.18~rc2

Revision ID: 5462f610384b
Revises: 8c3c7a90ada7
Create Date: 2026-10-30 09:15:14.441000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5462f610384b"
down_revision: Union[str, None] = "8c3c7a90ada7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.18~rc2' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.18~rc1' WHERE id = 1")
