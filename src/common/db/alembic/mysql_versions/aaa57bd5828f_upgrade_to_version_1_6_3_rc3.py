"""Upgrade to version 1.6.3-rc3

Revision ID: aaa57bd5828f
Revises: bd24b496a4e3
Create Date: 2025-07-30 10:43:35.503915

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aaa57bd5828f"
down_revision: Union[str, None] = "bd24b496a4e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.3-rc2
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc2' WHERE id = 1")
