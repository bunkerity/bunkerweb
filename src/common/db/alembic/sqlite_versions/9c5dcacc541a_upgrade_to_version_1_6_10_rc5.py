"""Upgrade to version 1.6.10~rc5

Revision ID: 9c5dcacc541a
Revises: 81ef5f1e4bf2
Create Date: 2026-05-04 15:57:47.059352

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9c5dcacc541a"
down_revision: Union[str, None] = "81ef5f1e4bf2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc5' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")
