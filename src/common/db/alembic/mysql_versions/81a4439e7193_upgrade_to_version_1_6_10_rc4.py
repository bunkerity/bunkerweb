"""Upgrade to version 1.6.10~rc4

Revision ID: 81a4439e7193
Revises: 81db6b219029
Create Date: 2026-04-24 14:57:24.563908

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81a4439e7193"
down_revision: Union[str, None] = "81db6b219029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc4' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.10~rc3
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc3' WHERE id = 1")
