"""Upgrade to version 1.6.2-rc3

Revision ID: 6963ee773ffc
Revises: 4e98a08c5902
Create Date: 2025-06-06 08:24:05.687630

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6963ee773ffc"
down_revision: Union[str, None] = "4e98a08c5902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc2' WHERE id = 1")
