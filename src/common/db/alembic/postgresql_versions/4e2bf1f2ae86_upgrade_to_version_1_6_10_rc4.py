"""Upgrade to version 1.6.10~rc4

Revision ID: 4e2bf1f2ae86
Revises: e4f3ef364f5c
Create Date: 2026-04-24 15:01:08.389400

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e2bf1f2ae86"
down_revision: Union[str, None] = "e4f3ef364f5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.10~rc3
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")
