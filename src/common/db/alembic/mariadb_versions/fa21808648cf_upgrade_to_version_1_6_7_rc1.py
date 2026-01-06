"""Upgrade to version 1.6.7~rc1

Revision ID: fa21808648cf
Revises: 8a140aff73dd
Create Date: 2025-12-16 14:47:16.317795

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "fa21808648cf"
down_revision: Union[str, None] = "8a140aff73dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_custom_configs", sa.Column("is_draft", sa.Boolean(), server_default="0", nullable=False))

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7~rc1' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_custom_configs", "is_draft")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.6' WHERE id = 1")
