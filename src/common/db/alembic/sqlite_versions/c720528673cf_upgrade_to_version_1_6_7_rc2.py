"""Upgrade to version 1.6.7~rc2

Revision ID: c720528673cf
Revises: 2e3e5668c409
Create Date: 2026-01-06 16:51:39.333560

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c720528673cf"
down_revision: Union[str, None] = "2e3e5668c409"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc1' WHERE id = 1")
