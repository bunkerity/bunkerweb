"""Upgrade to version 1.6.12

Revision ID: b4e0d05e52e7
Revises: b9f07319d7ab
Create Date: 2026-06-22 13:49:31.379436

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e0d05e52e7"
down_revision: Union[str, None] = "b9f07319d7ab"
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
