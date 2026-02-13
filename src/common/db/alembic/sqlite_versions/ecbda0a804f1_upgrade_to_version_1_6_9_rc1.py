"""Upgrade to version 1.6.9~rc1

Revision ID: ecbda0a804f1
Revises: bf32ccd17258
Create Date: 2026-02-13 19:48:48.708957

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ecbda0a804f1"
down_revision: Union[str, None] = "bf32ccd17258"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8' WHERE id = 1")
