"""Upgrade to version 1.6.10~rc2

Revision ID: e992b519fd19
Revises: 465f32a2ade4
Create Date: 2026-03-27 18:12:31.035917

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e992b519fd19"
down_revision: Union[str, None] = "465f32a2ade4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc1' WHERE id = 1")
