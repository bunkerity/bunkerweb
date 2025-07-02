"""Upgrade to version 1.6.2

Revision ID: 19f614532015
Revises: 54f8933f6290
Create Date: 2025-07-02 08:06:45.957545

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19f614532015"
down_revision: Union[str, None] = "54f8933f6290"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc7' WHERE id = 1")
