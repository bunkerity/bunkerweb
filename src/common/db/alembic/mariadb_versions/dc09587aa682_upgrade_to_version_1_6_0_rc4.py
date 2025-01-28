"""Upgrade to version 1.6.0-rc4

Revision ID: dc09587aa682
Revises: 28d521ac2009
Create Date: 2025-01-28 08:41:56.481003

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "dc09587aa682"
down_revision: Union[str, None] = "28d521ac2009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc3' WHERE id = 1")
