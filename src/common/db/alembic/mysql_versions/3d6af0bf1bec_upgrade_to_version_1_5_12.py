"""Upgrade to version 1.5.12

Revision ID: 3d6af0bf1bec
Revises: 12ffcd2b9d63
Create Date: 2024-12-19 13:32:27.783961

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "3d6af0bf1bec"
down_revision: Union[str, None] = "12ffcd2b9d63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version to 1.5.12
    op.execute("UPDATE bw_metadata SET version = '1.5.12' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.5.11
    op.execute("UPDATE bw_metadata SET version = '1.5.11' WHERE id = 1")
