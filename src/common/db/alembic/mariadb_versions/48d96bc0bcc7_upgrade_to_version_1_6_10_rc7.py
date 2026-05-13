"""Upgrade to version 1.6.10~rc7

Revision ID: 48d96bc0bcc7
Revises: dcd7a1448119
Create Date: 2026-05-13 11:51:55.379223

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48d96bc0bcc7"
down_revision: Union[str, None] = "dcd7a1448119"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc7' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc6' WHERE id = 1")
