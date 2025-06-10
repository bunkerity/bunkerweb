"""Upgrade to version 1.6.2-rc3

Revision ID: 5db76033c2ab
Revises: af0874aa3072
Create Date: 2025-06-06 08:27:03.074446

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5db76033c2ab"
down_revision: Union[str, None] = "af0874aa3072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc2' WHERE id = 1")
