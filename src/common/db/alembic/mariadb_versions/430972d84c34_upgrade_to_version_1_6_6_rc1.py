"""Upgrade to version 1.6.6-rc1

Revision ID: 430972d84c34
Revises: be8fd745e43c
Create Date: 2025-10-30 08:39:45.697062

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "430972d84c34"
down_revision: Union[str, None] = "be8fd745e43c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5' WHERE id = 1")
