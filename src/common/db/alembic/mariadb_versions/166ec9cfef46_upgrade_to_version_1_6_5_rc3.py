"""Upgrade to version 1.6.5-rc3

Revision ID: 166ec9cfef46
Revises: d97f19935f96
Create Date: 2025-09-11 13:39:00.972299

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "166ec9cfef46"
down_revision: Union[str, None] = "d97f19935f96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc2' WHERE id = 1")
