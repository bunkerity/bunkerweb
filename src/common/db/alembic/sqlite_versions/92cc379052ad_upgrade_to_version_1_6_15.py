"""Upgrade to version 1.6.15

Revision ID: 92cc379052ad
Revises: 7bdd2a9f3786
Create Date: 2026-09-18 20:02:21.237258

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "92cc379052ad"
down_revision: Union[str, None] = "7bdd2a9f3786"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.15' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc3' WHERE id = 1")
