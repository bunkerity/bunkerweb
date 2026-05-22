"""Upgrade to version 1.6.10~rc7

Revision ID: 30862abba879
Revises: 4d48b391ee8c
Create Date: 2026-05-13 11:29:13.871695

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "30862abba879"
down_revision: Union[str, None] = "4d48b391ee8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc7' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc6' WHERE id = 1")
