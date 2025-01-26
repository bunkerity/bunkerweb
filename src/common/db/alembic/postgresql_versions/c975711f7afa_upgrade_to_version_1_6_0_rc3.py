"""Upgrade to version 1.6.0-rc3

Revision ID: c975711f7afa
Revises: b56eb8d8dbf2
Create Date: 2025-01-22 16:22:47.058243

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c975711f7afa"
down_revision: Union[str, None] = "b56eb8d8dbf2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc2' WHERE id = 1")
