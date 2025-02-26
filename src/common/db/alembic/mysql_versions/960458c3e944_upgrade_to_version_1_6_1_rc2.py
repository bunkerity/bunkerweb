"""Upgrade to version 1.6.1-rc2

Revision ID: 960458c3e944
Revises: 0600f2ed826f
Create Date: 2025-02-26 10:23:51.088128

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "960458c3e944"
down_revision: Union[str, None] = "0600f2ed826f"
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
