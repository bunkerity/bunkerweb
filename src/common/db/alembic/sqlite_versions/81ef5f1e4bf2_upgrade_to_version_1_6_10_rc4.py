"""Upgrade to version 1.6.10~rc4

Revision ID: 81ef5f1e4bf2
Revises: e2e2207cf9eb
Create Date: 2026-04-24 14:46:09.116309

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81ef5f1e4bf2"
down_revision: Union[str, None] = "e2e2207cf9eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.10~rc3
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")
