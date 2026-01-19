"""Upgrade to version 1.6.8~rc1

Revision ID: 7ba2eb8412ef
Revises: 761dfbaa7397
Create Date: 2026-01-16 16:52:16.587638

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7ba2eb8412ef"
down_revision: Union[str, None] = "761dfbaa7397"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7' WHERE id = 1")
