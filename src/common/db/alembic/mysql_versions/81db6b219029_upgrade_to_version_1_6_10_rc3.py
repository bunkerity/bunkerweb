"""Upgrade to version 1.6.10~rc3

Revision ID: 81db6b219029
Revises: d2bb8a70b034
Create Date: 2026-04-11 07:07:02.729294

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81db6b219029"
down_revision: Union[str, None] = "d2bb8a70b034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc2' WHERE id = 1")
