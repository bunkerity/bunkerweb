"""Upgrade to version 1.6.11

Revision ID: 86df1ee4c3c4
Revises: 8cecdd277611
Create Date: 2026-05-23 10:01:29.112791

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "86df1ee4c3c4"
down_revision: Union[str, None] = "8cecdd277611"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11~rc1' WHERE id = 1")
