"""Upgrade to version 1.5.12

Revision ID: 0229aafe5e96
Revises: bf07e30a9b65
Create Date: 2024-12-17 15:06:45.746107

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "0229aafe5e96"
down_revision: Union[str, None] = "bf07e30a9b65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version to 1.5.12
    op.execute("UPDATE bw_metadata SET version = '1.5.12' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.5.11
    op.execute("UPDATE bw_metadata SET version = '1.5.11' WHERE id = 1")
