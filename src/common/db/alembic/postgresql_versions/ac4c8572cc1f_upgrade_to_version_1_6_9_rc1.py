"""Upgrade to version 1.6.9~rc1

Revision ID: ac4c8572cc1f
Revises: 1b8164b8905e
Create Date: 2026-02-13 20:09:50.303564

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ac4c8572cc1f"
down_revision: Union[str, None] = "1b8164b8905e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8' WHERE id = 1")
