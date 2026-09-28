"""Upgrade to version 1.6.10~rc3

Revision ID: e2e2207cf9eb
Revises: ad5908b91c3d
Create Date: 2026-04-11 07:05:15.530616

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2e2207cf9eb"
down_revision: Union[str, None] = "ad5908b91c3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc2' WHERE id = 1")
