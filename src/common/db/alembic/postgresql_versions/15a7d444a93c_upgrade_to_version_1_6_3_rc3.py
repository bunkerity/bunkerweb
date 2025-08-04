"""Upgrade to version 1.6.3-rc3

Revision ID: 15a7d444a93c
Revises: 8c91e2dd3a8b
Create Date: 2025-07-30 10:47:30.047890

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "15a7d444a93c"
down_revision: Union[str, None] = "8c91e2dd3a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.3-rc2
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc2' WHERE id = 1")
