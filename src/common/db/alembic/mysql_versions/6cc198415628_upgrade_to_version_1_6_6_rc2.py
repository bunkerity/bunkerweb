"""Upgrade to version 1.6.6-rc2

Revision ID: 6cc198415628
Revises: 1fbcf98452fc
Create Date: 2025-11-05 14:33:15.699905

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6cc198415628"
down_revision: Union[str, None] = "1fbcf98452fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc1' WHERE id = 1")
