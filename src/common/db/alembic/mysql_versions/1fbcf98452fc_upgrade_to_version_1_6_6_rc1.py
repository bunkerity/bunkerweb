"""Upgrade to version 1.6.6-rc1

Revision ID: 1fbcf98452fc
Revises: 545f27ae0694
Create Date: 2025-10-30 08:52:20.433326

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1fbcf98452fc"
down_revision: Union[str, None] = "545f27ae0694"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5' WHERE id = 1")
