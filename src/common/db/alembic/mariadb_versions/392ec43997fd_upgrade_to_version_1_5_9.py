"""Upgrade to version 1.5.9

Revision ID: 392ec43997fd
Revises: 0949ce7a3875
Create Date: 2024-12-17 15:06:36.162645

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "392ec43997fd"
down_revision: Union[str, None] = "0949ce7a3875"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.8' WHERE id = 1")
