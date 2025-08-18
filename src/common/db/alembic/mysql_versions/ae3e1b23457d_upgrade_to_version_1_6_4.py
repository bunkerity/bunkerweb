"""Upgrade to version 1.6.4

Revision ID: ae3e1b23457d
Revises: 4f46305855fd
Create Date: 2025-08-18 09:33:26.328262

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ae3e1b23457d"
down_revision: Union[str, None] = "4f46305855fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3' WHERE id = 1")
