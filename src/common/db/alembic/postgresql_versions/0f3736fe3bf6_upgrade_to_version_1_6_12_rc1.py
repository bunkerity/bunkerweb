"""Upgrade to version 1.6.12~rc1

Revision ID: 0f3736fe3bf6
Revises: 86df1ee4c3c4
Create Date: 2026-05-29 14:50:33.192195

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f3736fe3bf6"
down_revision: Union[str, None] = "86df1ee4c3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11' WHERE id = 1")
