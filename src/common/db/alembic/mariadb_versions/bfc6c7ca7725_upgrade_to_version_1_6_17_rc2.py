"""Upgrade to version 1.6.17~rc2

Revision ID: bfc6c7ca7725
Revises: ee638d4e1982
Create Date: 2026-10-16 15:22:33.638933

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bfc6c7ca7725"
down_revision: Union[str, None] = "ee638d4e1982"
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
