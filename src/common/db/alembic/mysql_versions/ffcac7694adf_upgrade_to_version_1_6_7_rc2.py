"""Upgrade to version 1.6.7~rc2

Revision ID: ffcac7694adf
Revises: e4d104385f4a
Create Date: 2026-01-06 16:59:01.955527

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ffcac7694adf"
down_revision: Union[str, None] = "e4d104385f4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc1' WHERE id = 1")
