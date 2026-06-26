"""Upgrade to version 1.6.12~rc3

Revision ID: 3f9ca740b2cb
Revises: 65ec26787f9f
Create Date: 2026-06-18 17:07:32.685290

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f9ca740b2cb"
down_revision: Union[str, None] = "65ec26787f9f"
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
