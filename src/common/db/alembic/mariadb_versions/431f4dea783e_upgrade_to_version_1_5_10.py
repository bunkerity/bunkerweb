"""Upgrade to version 1.5.10

Revision ID: 431f4dea783e
Revises: 392ec43997fd
Create Date: 2024-12-17 15:06:39.416494

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "431f4dea783e"
down_revision: Union[str, None] = "392ec43997fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.10' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata' back to 1.5.9
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")
