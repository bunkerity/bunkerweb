"""Upgrade to version 1.6.2-rc6

Revision ID: 882817d21966
Revises: 11f9c4ead1cf
Create Date: 2025-06-18 07:20:45.164344

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "882817d21966"
down_revision: Union[str, None] = "11f9c4ead1cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc6' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc5' WHERE id = 1")
