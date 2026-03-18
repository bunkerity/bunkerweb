"""Upgrade to version 1.6.9~rc3

Revision ID: e7ab450531c2
Revises: 7b000e03cdcd
Create Date: 2026-03-06 16:02:20.049649

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7ab450531c2"
down_revision: Union[str, None] = "7b000e03cdcd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc2' WHERE id = 1")
