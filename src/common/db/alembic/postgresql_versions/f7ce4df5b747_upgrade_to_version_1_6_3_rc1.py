"""Upgrade to version 1.6.3-rc1

Revision ID: f7ce4df5b747
Revises: 19f614532015
Create Date: 2025-07-29 06:09:48.686436

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f7ce4df5b747"
down_revision: Union[str, None] = "19f614532015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.2
    op.execute("UPDATE bw_metadata SET version = '1.6.2' WHERE id = 1")
