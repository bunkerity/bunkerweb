"""Upgrade to version 1.6.16~rc4

Revision ID: 3c9aec4c71ed
Revises: 12ef59ef5afe
Create Date: 2026-10-06 08:49:39.731417

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c9aec4c71ed"
down_revision: Union[str, None] = "12ef59ef5afe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16~rc4' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16~rc3' WHERE id = 1")
