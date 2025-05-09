"""Upgrade to version 1.6.1-rc2

Revision ID: 07f8fe23ccb5
Revises: 864a1dbd2430
Create Date: 2025-02-26 10:20:28.081873

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "07f8fe23ccb5"
down_revision: Union[str, None] = "864a1dbd2430"
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
