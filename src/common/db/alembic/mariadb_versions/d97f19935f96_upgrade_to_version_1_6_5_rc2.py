"""Upgrade to version 1.6.5-rc2

Revision ID: d97f19935f96
Revises: 9e5ffbdea725
Create Date: 2025-09-05 16:38:48.117611

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d97f19935f96"
down_revision: Union[str, None] = "9e5ffbdea725"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc1' WHERE id = 1")
