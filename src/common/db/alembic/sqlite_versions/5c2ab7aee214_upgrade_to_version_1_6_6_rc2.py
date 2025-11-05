"""Upgrade to version 1.6.6-rc2

Revision ID: 5c2ab7aee214
Revises: a6addd792bf3
Create Date: 2025-11-05 14:27:50.694841

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5c2ab7aee214"
down_revision: Union[str, None] = "a6addd792bf3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc1' WHERE id = 1")
