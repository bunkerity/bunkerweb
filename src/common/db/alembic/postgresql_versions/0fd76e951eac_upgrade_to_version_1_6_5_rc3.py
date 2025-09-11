"""Upgrade to version 1.6.5-rc3

Revision ID: 0fd76e951eac
Revises: 72a2a0276a1c
Create Date: 2025-09-11 13:42:23.136769

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0fd76e951eac"
down_revision: Union[str, None] = "72a2a0276a1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc2' WHERE id = 1")
