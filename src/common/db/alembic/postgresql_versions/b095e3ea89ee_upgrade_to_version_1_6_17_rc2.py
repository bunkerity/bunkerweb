"""Upgrade to version 1.6.17~rc2

Revision ID: b095e3ea89ee
Revises: 8053e91a84bc
Create Date: 2026-10-16 15:22:33.741329

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b095e3ea89ee"
down_revision: Union[str, None] = "8053e91a84bc"
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
