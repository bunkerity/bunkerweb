"""Upgrade to version 1.5.9

Revision ID: c6fcd4f6971d
Revises: b45f98a50b5c
Create Date: 2024-12-19 13:27:29.252130

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "c6fcd4f6971d"
down_revision: Union[str, None] = "b45f98a50b5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.8' WHERE id = 1")
