"""Upgrade to version 1.6.7~rc2

Revision ID: 9fd808d31d16
Revises: fa21808648cf
Create Date: 2026-01-06 16:54:43.984916

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9fd808d31d16"
down_revision: Union[str, None] = "fa21808648cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc1' WHERE id = 1")
