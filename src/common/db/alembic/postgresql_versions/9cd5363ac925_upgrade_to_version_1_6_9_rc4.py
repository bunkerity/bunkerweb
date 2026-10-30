"""Upgrade to version 1.6.9~rc4

Revision ID: 9cd5363ac925
Revises: 76f9690120e4
Create Date: 2026-03-10 08:22:03.231362

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9cd5363ac925"
down_revision: Union[str, None] = "76f9690120e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc3' WHERE id = 1")
