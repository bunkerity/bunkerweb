"""Upgrade to version 1.6.9~rc3

Revision ID: 76f9690120e4
Revises: 32d89d02c8e5
Create Date: 2026-03-06 16:08:45.049257

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "76f9690120e4"
down_revision: Union[str, None] = "32d89d02c8e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc2' WHERE id = 1")
