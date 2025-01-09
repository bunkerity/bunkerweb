"""Upgrade to version 1.5.3

Revision ID: eb3ca0f3f20c
Revises: 259e352699f1
Create Date: 2024-12-17 08:38:04.878280

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "eb3ca0f3f20c"
down_revision: Union[str, None] = "259e352699f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data migration: Update the version to 1.5.3
    op.execute("UPDATE bw_metadata SET version = '1.5.3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version back to 1.5.2
    op.execute("UPDATE bw_metadata SET version = '1.5.2' WHERE id = 1")
