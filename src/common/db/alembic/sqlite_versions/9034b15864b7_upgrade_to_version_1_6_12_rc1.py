"""Upgrade to version 1.6.12~rc1

Revision ID: 9034b15864b7
Revises: 20966abcdf3e
Create Date: 2026-05-29 14:47:46.510141

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9034b15864b7"
down_revision: Union[str, None] = "20966abcdf3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11' WHERE id = 1")
