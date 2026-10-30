"""Upgrade to version 1.6.10~rc4

Revision ID: 7975fc12c5ca
Revises: c58696cfa84b
Create Date: 2026-04-24 14:51:30.040281

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7975fc12c5ca"
down_revision: Union[str, None] = "c58696cfa84b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.10~rc3
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")
