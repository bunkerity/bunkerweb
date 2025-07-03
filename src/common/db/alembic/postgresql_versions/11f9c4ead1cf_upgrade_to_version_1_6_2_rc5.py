"""Upgrade to version 1.6.2-rc5

Revision ID: 11f9c4ead1cf
Revises: d15ee0d0f93a
Create Date: 2025-06-13 16:02:31.101247

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "11f9c4ead1cf"
down_revision: Union[str, None] = "d15ee0d0f93a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc5' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc4' WHERE id = 1")
