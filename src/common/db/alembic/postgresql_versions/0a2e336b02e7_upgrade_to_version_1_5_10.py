"""Upgrade to version 1.5.10

Revision ID: 0a2e336b02e7
Revises: fe047f892d6b
Create Date: 2024-12-19 14:42:04.961295

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0a2e336b02e7"
down_revision: Union[str, None] = "fe047f892d6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.10' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata' back to 1.5.9
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")
