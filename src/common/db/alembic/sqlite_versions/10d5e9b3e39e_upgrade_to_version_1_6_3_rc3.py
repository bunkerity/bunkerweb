"""Upgrade to version 1.6.3-rc3

Revision ID: 10d5e9b3e39e
Revises: 940d4e056335
Create Date: 2025-07-30 10:30:39.831963

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "10d5e9b3e39e"
down_revision: Union[str, None] = "940d4e056335"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.3-rc2
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc2' WHERE id = 1")
