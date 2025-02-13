"""Upgrade to version 1.6.0

Revision ID: f85e36780e55
Revises: 7939f7165327
Create Date: 2025-02-13 10:12:21.005719

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f85e36780e55"
down_revision: Union[str, None] = "7939f7165327"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc4' WHERE id = 1")
