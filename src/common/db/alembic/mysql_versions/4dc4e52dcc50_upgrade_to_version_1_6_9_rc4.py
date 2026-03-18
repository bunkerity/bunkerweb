"""Upgrade to version 1.6.9~rc4

Revision ID: 4dc4e52dcc50
Revises: e7ab450531c2
Create Date: 2026-03-10 08:16:56.008863

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4dc4e52dcc50"
down_revision: Union[str, None] = "e7ab450531c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")
