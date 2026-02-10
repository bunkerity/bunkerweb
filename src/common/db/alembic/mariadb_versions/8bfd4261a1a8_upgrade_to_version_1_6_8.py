"""Upgrade to version 1.6.8

Revision ID: 8bfd4261a1a8
Revises: 1a828a499ec1
Create Date: 2026-02-06 09:22:22.939338

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8bfd4261a1a8"
down_revision: Union[str, None] = "1a828a499ec1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc3' WHERE id = 1")
