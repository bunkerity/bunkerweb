"""Upgrade to version 1.6.13~rc1

Revision ID: 46dfe9f35352
Revises: 0fe0711317f9
Create Date: 2026-07-10 18:51:51.708675

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "46dfe9f35352"
down_revision: Union[str, None] = "0fe0711317f9"
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
