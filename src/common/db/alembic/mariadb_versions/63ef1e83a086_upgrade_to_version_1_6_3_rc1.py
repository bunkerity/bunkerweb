"""Upgrade to version 1.6.3-rc1

Revision ID: 63ef1e83a086
Revises: 78e81bf472ac
Create Date: 2025-07-28 10:01:16.901896

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "63ef1e83a086"
down_revision: Union[str, None] = "78e81bf472ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.2
    op.execute("UPDATE bw_metadata SET version = '1.6.2' WHERE id = 1")
