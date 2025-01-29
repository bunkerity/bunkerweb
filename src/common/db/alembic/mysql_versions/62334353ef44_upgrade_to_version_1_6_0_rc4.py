"""Upgrade to version 1.6.0-rc4

Revision ID: 62334353ef44
Revises: 53accecd001e
Create Date: 2025-01-28 08:46:12.180358

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "62334353ef44"
down_revision: Union[str, None] = "53accecd001e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc3' WHERE id = 1")
