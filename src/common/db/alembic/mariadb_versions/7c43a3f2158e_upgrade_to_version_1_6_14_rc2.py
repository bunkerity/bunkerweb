"""Upgrade to version 1.6.14~rc2

Revision ID: 7c43a3f2158e
Revises: d68c293ef7ab
Create Date: 2026-07-28 14:58:06.895833

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c43a3f2158e"
down_revision: Union[str, None] = "d68c293ef7ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.14~rc2' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.14~rc1' WHERE id = 1")
