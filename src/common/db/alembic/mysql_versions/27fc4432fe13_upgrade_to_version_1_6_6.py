"""Upgrade to version 1.6.6

Revision ID: 27fc4432fe13
Revises: 3cd0b5d6abc9
Create Date: 2025-11-22 13:02:42.263647

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27fc4432fe13"
down_revision: Union[str, None] = "3cd0b5d6abc9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6-rc3' WHERE id = 1")
