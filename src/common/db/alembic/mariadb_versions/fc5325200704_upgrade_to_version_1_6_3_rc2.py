"""Upgrade to version 1.6.3-rc2

Revision ID: fc5325200704
Revises: 63ef1e83a086
Create Date: 2025-07-29 06:20:15.015214

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "fc5325200704"
down_revision: Union[str, None] = "63ef1e83a086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.3-rc1
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc1' WHERE id = 1")
