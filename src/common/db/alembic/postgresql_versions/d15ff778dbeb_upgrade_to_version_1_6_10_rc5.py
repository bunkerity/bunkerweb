"""Upgrade to version 1.6.10~rc5

Revision ID: d15ff778dbeb
Revises: 4e2bf1f2ae86
Create Date: 2026-05-04 16:02:28.686534

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d15ff778dbeb"
down_revision: Union[str, None] = "4e2bf1f2ae86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc5' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")
