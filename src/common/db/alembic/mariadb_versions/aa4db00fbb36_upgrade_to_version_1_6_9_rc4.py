"""Upgrade to version 1.6.9~rc4

Revision ID: aa4db00fbb36
Revises: aac5ae14585c
Create Date: 2026-03-10 08:11:50.243881

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa4db00fbb36"
down_revision: Union[str, None] = "aac5ae14585c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")
