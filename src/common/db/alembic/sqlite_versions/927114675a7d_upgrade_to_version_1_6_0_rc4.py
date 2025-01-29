"""Upgrade to version 1.6.0-rc4

Revision ID: 927114675a7d
Revises: 76ce66b69597
Create Date: 2025-01-28 08:40:10.562006

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "927114675a7d"
down_revision: Union[str, None] = "76ce66b69597"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc3' WHERE id = 1")
