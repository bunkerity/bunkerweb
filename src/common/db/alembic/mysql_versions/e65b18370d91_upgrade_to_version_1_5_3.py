"""Upgrade to version 1.5.3

Revision ID: e65b18370d91
Revises: e4ccc523fea5
Create Date: 2024-12-19 13:18:36.153688

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "e65b18370d91"
down_revision: Union[str, None] = "e4ccc523fea5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data migration: Update the version to 1.5.3
    op.execute("UPDATE bw_metadata SET version = '1.5.3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version back to 1.5.2
    op.execute("UPDATE bw_metadata SET version = '1.5.2' WHERE id = 1")
