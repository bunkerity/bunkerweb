"""Upgrade to version 1.5.9

Revision ID: fe047f892d6b
Revises: ba43081c6f96
Create Date: 2024-12-19 14:41:12.553100

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fe047f892d6b"
down_revision: Union[str, None] = "ba43081c6f96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.8' WHERE id = 1")
