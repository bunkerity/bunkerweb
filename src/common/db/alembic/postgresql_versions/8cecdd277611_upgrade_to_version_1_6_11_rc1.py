"""Upgrade to version 1.6.11~rc1

Revision ID: 8cecdd277611
Revises: dc32f5dabb70
Create Date: 2026-05-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8cecdd277611"
down_revision: Union[str, None] = "dc32f5dabb70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10' WHERE id = 1")
