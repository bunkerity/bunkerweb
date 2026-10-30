"""Upgrade to version 1.6.15~rc1

Revision ID: 82bf69b29509
Revises: 85241481d5a4
Create Date: 2026-08-31 12:07:50.151532

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82bf69b29509"
down_revision: Union[str, None] = "85241481d5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc1' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.14' WHERE id = 1")
