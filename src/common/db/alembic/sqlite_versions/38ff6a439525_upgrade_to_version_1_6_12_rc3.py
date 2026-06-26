"""Upgrade to version 1.6.12~rc3

Revision ID: 38ff6a439525
Revises: f8c0912c8f34
Create Date: 2026-06-18 16:58:58.030240

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "38ff6a439525"
down_revision: Union[str, None] = "f8c0912c8f34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc3' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc2' WHERE id = 1")
