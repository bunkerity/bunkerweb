"""Upgrade to version 1.6.3-rc2

Revision ID: bd24b496a4e3
Revises: c56f10a148e9
Create Date: 2025-07-29 06:22:00.362781

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bd24b496a4e3"
down_revision: Union[str, None] = "c56f10a148e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.3-rc1
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc1' WHERE id = 1")
