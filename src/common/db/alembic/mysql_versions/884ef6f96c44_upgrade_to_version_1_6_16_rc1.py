"""Upgrade to version 1.6.16~rc1

Revision ID: 884ef6f96c44
Revises: 9f5c8bc80fe0
Create Date: 2026-09-21 13:12:46.716644

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "884ef6f96c44"
down_revision: Union[str, None] = "9f5c8bc80fe0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16~rc1' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.15' WHERE id = 1")
