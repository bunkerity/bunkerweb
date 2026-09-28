"""Upgrade to version 1.6.10

Revision ID: c6673c17e477
Revises: a6fd7a8c037f
Create Date: 2026-05-15 15:49:23.329406

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c6673c17e477"
down_revision: Union[str, None] = "a6fd7a8c037f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc7' WHERE id = 1")
