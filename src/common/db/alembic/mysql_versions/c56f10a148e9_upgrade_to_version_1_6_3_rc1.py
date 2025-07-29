"""Upgrade to version 1.6.3-rc1

Revision ID: c56f10a148e9
Revises: 59e19dabe323
Create Date: 2025-07-29 06:06:06.640421

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c56f10a148e9"
down_revision: Union[str, None] = "59e19dabe323"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.2
    op.execute("UPDATE bw_metadata SET version = '1.6.2' WHERE id = 1")
