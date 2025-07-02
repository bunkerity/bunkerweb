"""Upgrade to version 1.6.2

Revision ID: 78e81bf472ac
Revises: 522ba97eba84
Create Date: 2025-07-02 07:47:57.518390

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "78e81bf472ac"
down_revision: Union[str, None] = "522ba97eba84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc7' WHERE id = 1")
