"""Upgrade to version 1.6.3

Revision ID: 5eed3c0a192e
Revises: 15a7d444a93c
Create Date: 2025-08-04 08:41:25.108688

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5eed3c0a192e"
down_revision: Union[str, None] = "15a7d444a93c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc3' WHERE id = 1")
