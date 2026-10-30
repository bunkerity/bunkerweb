"""Upgrade to version 1.6.11

Revision ID: a48eacc5e5b6
Revises: 88edf42fd04e
Create Date: 2026-05-23 10:00:43.788959

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a48eacc5e5b6"
down_revision: Union[str, None] = "88edf42fd04e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11~rc1' WHERE id = 1")
