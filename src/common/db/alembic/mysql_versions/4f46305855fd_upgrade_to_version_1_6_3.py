"""Upgrade to version 1.6.3

Revision ID: 4f46305855fd
Revises: aaa57bd5828f
Create Date: 2025-08-04 08:39:04.876450

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f46305855fd"
down_revision: Union[str, None] = "aaa57bd5828f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc3' WHERE id = 1")
