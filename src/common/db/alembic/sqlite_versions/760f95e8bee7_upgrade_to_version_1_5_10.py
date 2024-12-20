"""Upgrade to version 1.5.10

Revision ID: 760f95e8bee7
Revises: 4f7bdc32c662
Create Date: 2024-12-17 08:41:39.621642

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "760f95e8bee7"
down_revision: Union[str, None] = "4f7bdc32c662"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.10' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata' back to 1.5.9
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")
