"""Upgrade to version 1.6.3-rc2

Revision ID: 8c91e2dd3a8b
Revises: f7ce4df5b747
Create Date: 2025-07-29 06:23:39.110675

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8c91e2dd3a8b"
down_revision: Union[str, None] = "f7ce4df5b747"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.3-rc1
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc1' WHERE id = 1")
