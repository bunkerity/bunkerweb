"""Upgrade to version 1.6.8~rc1

Revision ID: 4a135a1ec0fe
Revises: 1e3b377594f6
Create Date: 2026-01-16 17:04:24.006680

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a135a1ec0fe"
down_revision: Union[str, None] = "1e3b377594f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7' WHERE id = 1")
