"""Upgrade to version 1.6.12

Revision ID: f9c3d7b2dba8
Revises: 38ff6a439525
Create Date: 2026-06-22 13:46:13.624483

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c3d7b2dba8"
down_revision: Union[str, None] = "38ff6a439525"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc3' WHERE id = 1")
