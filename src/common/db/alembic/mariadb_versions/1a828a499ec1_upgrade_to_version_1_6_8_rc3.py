"""Upgrade to version 1.6.8~rc3

Revision ID: 1a828a499ec1
Revises: 002e685396c1
Create Date: 2026-01-30 12:17:07.970320

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1a828a499ec1"
down_revision: Union[str, None] = "002e685396c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc2' WHERE id = 1")
