"""Upgrade to version 1.6.8~rc3

Revision ID: 9052567b5843
Revises: 58c939808472
Create Date: 2026-01-30 12:16:47.455294

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9052567b5843"
down_revision: Union[str, None] = "58c939808472"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc2' WHERE id = 1")
