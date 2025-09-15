"""Upgrade to version 1.6.5-rc3

Revision ID: fd214d08928f
Revises: 7a8df0c89512
Create Date: 2025-09-11 13:36:35.392256

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fd214d08928f"
down_revision: Union[str, None] = "7a8df0c89512"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc2' WHERE id = 1")
