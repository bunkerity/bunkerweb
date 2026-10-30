"""Upgrade to version 1.6.10~rc3

Revision ID: e4f3ef364f5c
Revises: 94b30311d26c
Create Date: 2026-04-11 07:08:42.769206

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f3ef364f5c"
down_revision: Union[str, None] = "94b30311d26c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc2' WHERE id = 1")
