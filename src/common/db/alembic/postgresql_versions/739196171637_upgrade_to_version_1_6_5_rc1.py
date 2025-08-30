"""Upgrade to version 1.6.5-rc1

Revision ID: 739196171637
Revises: cf17ba9f0d5f
Create Date: 2025-08-29 12:18:55.338210

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "739196171637"
down_revision: Union[str, None] = "cf17ba9f0d5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_metadata", sa.Column("force_pro_update", sa.Boolean(), nullable=True))
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc1' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_metadata", "force_pro_update")
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.4' WHERE id = 1")
