"""Upgrade to version 1.6.6-rc1

Revision ID: a6addd792bf3
Revises: a06ce1d36991
Create Date: 2025-10-30 08:24:23.888059

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a6addd792bf3"
down_revision: Union[str, None] = "a06ce1d36991"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5' WHERE id = 1")
