"""Upgrade to version 1.6.10~rc2

Revision ID: 94b30311d26c
Revises: 74557875b1f5
Create Date: 2026-03-27 18:16:51.029234

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94b30311d26c"
down_revision: Union[str, None] = "74557875b1f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc1' WHERE id = 1")
