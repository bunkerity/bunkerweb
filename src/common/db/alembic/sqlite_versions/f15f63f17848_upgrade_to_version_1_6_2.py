"""Upgrade to version 1.6.2

Revision ID: f15f63f17848
Revises: 661729738984
Create Date: 2025-07-02 07:45:34.854795

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f15f63f17848"
down_revision: Union[str, None] = "661729738984"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc7' WHERE id = 1")
