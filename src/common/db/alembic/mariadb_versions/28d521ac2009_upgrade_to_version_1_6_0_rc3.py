"""Upgrade to version 1.6.0-rc3

Revision ID: 28d521ac2009
Revises: cb5750a9d1f7
Create Date: 2025-01-22 15:54:39.735240

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "28d521ac2009"
down_revision: Union[str, None] = "cb5750a9d1f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc2' WHERE id = 1")
