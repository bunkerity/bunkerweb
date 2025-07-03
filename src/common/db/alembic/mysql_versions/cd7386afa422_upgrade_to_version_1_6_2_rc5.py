"""Upgrade to version 1.6.2-rc5

Revision ID: cd7386afa422
Revises: 8d546dcb3f14
Create Date: 2025-06-13 15:56:59.173887

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd7386afa422"
down_revision: Union[str, None] = "8d546dcb3f14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc5' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc4' WHERE id = 1")
