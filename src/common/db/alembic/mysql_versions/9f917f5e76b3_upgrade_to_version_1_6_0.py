"""Upgrade to version 1.6.0

Revision ID: 9f917f5e76b3
Revises: 62334353ef44
Create Date: 2025-02-13 10:10:03.328525

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "9f917f5e76b3"
down_revision: Union[str, None] = "62334353ef44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc4' WHERE id = 1")
