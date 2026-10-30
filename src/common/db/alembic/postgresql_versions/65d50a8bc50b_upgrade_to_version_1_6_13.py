"""Upgrade to version 1.6.13

Revision ID: 65d50a8bc50b
Revises: 1df628a38b78
Create Date: 2026-07-16 10:47:49.742742

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65d50a8bc50b"
down_revision: Union[str, None] = "1df628a38b78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.13' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.13~rc1' WHERE id = 1")
