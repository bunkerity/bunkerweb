"""Upgrade to version 1.6.1-rc2

Revision ID: b2c34a5c2c67
Revises: 65b45de7eba5
Create Date: 2025-02-26 10:21:41.392451

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c34a5c2c67"
down_revision: Union[str, None] = "65b45de7eba5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_metadata", sa.Column("reload_ui_plugins", sa.Boolean(), nullable=True))
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_metadata", "reload_ui_plugins")
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1")
