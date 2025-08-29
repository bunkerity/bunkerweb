"""Upgrade to version 1.6.5-rc1

Revision ID: 9e5ffbdea725
Revises: c3cdd932e2b5
Create Date: 2025-08-29 11:54:52.086304

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9e5ffbdea725"
down_revision: Union[str, None] = "c3cdd932e2b5"
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
