"""Upgrade to version 1.5.9

Revision ID: 4f7bdc32c662
Revises: 13fb1f986f11
Create Date: 2024-12-17 08:41:37.205928

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f7bdc32c662"
down_revision: Union[str, None] = "13fb1f986f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.9' WHERE id = 1")


def downgrade() -> None:
    # Revert version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.8' WHERE id = 1")
