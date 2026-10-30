"""Upgrade to version 1.6.13~rc1

Revision ID: fe86913c3278
Revises: 8c6516301ef6
Create Date: 2026-07-10 18:52:41.366642

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fe86913c3278"
down_revision: Union[str, None] = "8c6516301ef6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.13~rc1' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12' WHERE id = 1")
