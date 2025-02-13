"""Upgrade to version 1.6.0

Revision ID: 5ceb08f3ea45
Revises: dc09587aa682
Create Date: 2025-02-13 10:06:13.753192

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5ceb08f3ea45"
down_revision: Union[str, None] = "dc09587aa682"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc4' WHERE id = 1")
