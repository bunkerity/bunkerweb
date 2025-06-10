"""Upgrade to version 1.6.2-rc3

Revision ID: cd5d566cc52d
Revises: 55e0b08b1270
Create Date: 2025-06-06 08:30:27.582081

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd5d566cc52d"
down_revision: Union[str, None] = "55e0b08b1270"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc2' WHERE id = 1")
