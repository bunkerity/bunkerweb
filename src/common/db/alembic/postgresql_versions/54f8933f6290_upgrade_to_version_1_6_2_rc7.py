"""Upgrade to version 1.6.2-rc7

Revision ID: 54f8933f6290
Revises: 882817d21966
Create Date: 2025-06-24 16:14:21.941457

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "54f8933f6290"
down_revision: Union[str, None] = "882817d21966"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE settings_types_enum ADD VALUE IF NOT EXISTS 'number'")
    op.execute("ALTER TYPE settings_types_enum ADD VALUE IF NOT EXISTS 'multivalue'")

    op.add_column("bw_settings", sa.Column("separator", sa.String(length=10), nullable=True))

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc7' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_settings", "separator")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc6' WHERE id = 1")
