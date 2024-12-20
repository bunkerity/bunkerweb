"""Upgrade to version 1.5.2

Revision ID: 259e352699f1
Revises: 6599b34870d1
Create Date: 2024-12-17 08:38:02.818323

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "259e352699f1"
down_revision: Union[str, None] = "6599b34870d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data migration: Update the version to 1.5.2
    op.execute("UPDATE bw_metadata SET version = '1.5.2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version back to 1.5.1
    op.execute("UPDATE bw_metadata SET version = '1.5.1' WHERE id = 1")
