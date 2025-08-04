"""Upgrade to version 1.6.3

Revision ID: b3717dab5cdf
Revises: 10d5e9b3e39e
Create Date: 2025-08-04 08:33:06.272471

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3717dab5cdf"
down_revision: Union[str, None] = "10d5e9b3e39e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc3' WHERE id = 1")
