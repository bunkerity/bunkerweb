"""Upgrade to version 1.5.10

Revision ID: b03a64d4d34a
Revises: c6fcd4f6971d
Create Date: 2024-12-19 13:28:59.190577

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "b03a64d4d34a"
down_revision: Union[str, None] = "c6fcd4f6971d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.10' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata' back to 1.5.9
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")
