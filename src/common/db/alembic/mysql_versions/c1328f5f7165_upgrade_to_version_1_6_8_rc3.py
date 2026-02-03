"""Upgrade to version 1.6.8~rc3

Revision ID: c1328f5f7165
Revises: d133bc8ef96d
Create Date: 2026-01-30 12:19:06.153317

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1328f5f7165"
down_revision: Union[str, None] = "d133bc8ef96d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc2' WHERE id = 1")
