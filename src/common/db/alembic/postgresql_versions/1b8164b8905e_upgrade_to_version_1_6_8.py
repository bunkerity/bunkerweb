"""Upgrade to version 1.6.8

Revision ID: 1b8164b8905e
Revises: c9c2b1bb33d6
Create Date: 2026-02-06 09:35:18.586810

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b8164b8905e"
down_revision: Union[str, None] = "c9c2b1bb33d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc3' WHERE id = 1")
