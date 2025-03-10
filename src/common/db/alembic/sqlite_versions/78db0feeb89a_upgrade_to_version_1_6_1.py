"""Upgrade to version 1.6.1

Revision ID: 78db0feeb89a
Revises: bb22be303c00
Create Date: 2025-03-10 08:26:38.911709

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "78db0feeb89a"
down_revision: Union[str, None] = "bb22be303c00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_metadata", sa.Column("failover_message", sa.TEXT(), nullable=True))

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_metadata", "failover_message")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc3' WHERE id = 1")
