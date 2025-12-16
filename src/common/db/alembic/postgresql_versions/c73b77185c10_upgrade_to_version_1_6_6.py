"""Upgrade to version 1.6.6

Revision ID: c73b77185c10
Revises: 9dc610f067ed
Create Date: 2025-11-22 13:10:12.996526

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c73b77185c10"
down_revision: Union[str, None] = "9dc610f067ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc3' WHERE id = 1")
