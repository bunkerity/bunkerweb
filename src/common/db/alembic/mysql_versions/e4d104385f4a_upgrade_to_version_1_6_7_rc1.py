"""Upgrade to version 1.6.7~rc1

Revision ID: e4d104385f4a
Revises: 27fc4432fe13
Create Date: 2025-12-16 14:55:39.940605

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e4d104385f4a"
down_revision: Union[str, None] = "27fc4432fe13"
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
