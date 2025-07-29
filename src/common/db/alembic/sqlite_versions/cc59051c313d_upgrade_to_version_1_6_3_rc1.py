"""Upgrade to version 1.6.3-rc1

Revision ID: cc59051c313d
Revises: f15f63f17848
Create Date: 2025-07-28 09:58:18.415118

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cc59051c313d"
down_revision: Union[str, None] = "f15f63f17848"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.2
    op.execute("UPDATE bw_metadata SET version = '1.6.2' WHERE id = 1")
