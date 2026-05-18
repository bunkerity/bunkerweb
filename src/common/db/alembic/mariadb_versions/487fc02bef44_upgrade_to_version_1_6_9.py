"""Upgrade to version 1.6.9

Revision ID: 487fc02bef44
Revises: aa4db00fbb36
Create Date: 2026-03-13 16:42:35.412033

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "487fc02bef44"
down_revision: Union[str, None] = "aa4db00fbb36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")
