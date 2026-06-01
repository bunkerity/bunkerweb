"""Upgrade to version 1.6.12~rc1

Revision ID: b0310ce7edd8
Revises: 07406d0af7c0
Create Date: 2026-05-29 14:48:56.887933

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0310ce7edd8"
down_revision: Union[str, None] = "07406d0af7c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11' WHERE id = 1")
