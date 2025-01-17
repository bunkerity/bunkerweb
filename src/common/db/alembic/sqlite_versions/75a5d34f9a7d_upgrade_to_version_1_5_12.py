"""Upgrade to version 1.5.12

Revision ID: 75a5d34f9a7d
Revises: c272a8c3979c
Create Date: 2024-12-17 08:42:31.548453

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "75a5d34f9a7d"
down_revision: Union[str, None] = "c272a8c3979c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version to 1.5.12
    op.execute("UPDATE bw_metadata SET version = '1.5.12' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.5.11
    op.execute("UPDATE bw_metadata SET version = '1.5.11' WHERE id = 1")
