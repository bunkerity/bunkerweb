"""Upgrade to version 1.6.17~rc1

Revision ID: ee638d4e1982
Revises: 4205feb82ee7
Create Date: 2026-10-14 18:23:16.323313

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ee638d4e1982"
down_revision: Union[str, None] = "4205feb82ee7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.17~rc1' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16' WHERE id = 1")
