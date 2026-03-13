"""Upgrade to version 1.6.9~rc3

Revision ID: 20cfd1a35c0e
Revises: 7194d17b0717
Create Date: 2026-03-06 15:50:19.315565

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20cfd1a35c0e"
down_revision: Union[str, None] = "7194d17b0717"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc2' WHERE id = 1")
