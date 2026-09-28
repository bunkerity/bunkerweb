"""Upgrade to version 1.6.10~rc1

Revision ID: 465f32a2ade4
Revises: 487fc02bef44
Create Date: 2026-03-23 15:30:04.740819

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "465f32a2ade4"
down_revision: Union[str, None] = "487fc02bef44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9' WHERE id = 1")
