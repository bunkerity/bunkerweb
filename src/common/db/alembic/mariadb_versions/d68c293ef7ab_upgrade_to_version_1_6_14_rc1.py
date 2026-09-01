"""Upgrade to version 1.6.14~rc1

Revision ID: d68c293ef7ab
Revises: 5412d3de3f3f
Create Date: 2026-07-22 10:01:39.794567

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d68c293ef7ab"
down_revision: Union[str, None] = "5412d3de3f3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.14~rc1' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.13' WHERE id = 1")
