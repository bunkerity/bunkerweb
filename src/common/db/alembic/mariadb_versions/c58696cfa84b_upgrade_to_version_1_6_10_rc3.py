"""Upgrade to version 1.6.10~rc3

Revision ID: c58696cfa84b
Revises: e992b519fd19
Create Date: 2026-04-11 07:05:34.468897

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c58696cfa84b"
down_revision: Union[str, None] = "e992b519fd19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc2' WHERE id = 1")
