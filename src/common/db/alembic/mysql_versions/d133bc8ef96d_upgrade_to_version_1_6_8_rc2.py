"""Upgrade to version 1.6.8~rc2

Revision ID: d133bc8ef96d
Revises: 327915db6e1d
Create Date: 2026-01-23 18:40:42.701703

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d133bc8ef96d"
down_revision: Union[str, None] = "327915db6e1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc1' WHERE id = 1")
