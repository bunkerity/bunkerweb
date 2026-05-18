"""Upgrade to version 1.6.8~rc2

Revision ID: 58c939808472
Revises: 7ba2eb8412ef
Create Date: 2026-01-23 16:35:20.013624

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "58c939808472"
down_revision: Union[str, None] = "7ba2eb8412ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc1' WHERE id = 1")
