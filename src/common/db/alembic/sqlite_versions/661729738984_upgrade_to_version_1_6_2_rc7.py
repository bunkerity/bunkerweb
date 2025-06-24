"""Upgrade to version 1.6.2-rc7

Revision ID: 661729738984
Revises: 9bf722264d33
Create Date: 2025-06-24 16:05:35.030106

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "661729738984"
down_revision: Union[str, None] = "9bf722264d33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_settings", sa.Column("separator", sa.String(length=10), nullable=True))

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc7' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_settings", "separator")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc6' WHERE id = 1")
