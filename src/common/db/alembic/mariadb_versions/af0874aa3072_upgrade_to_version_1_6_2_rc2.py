"""Upgrade to version 1.6.2-rc2

Revision ID: af0874aa3072
Revises: 89862729800d
Create Date: 2025-04-23 18:36:58.263462

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "af0874aa3072"
down_revision: Union[str, None] = "89862729800d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_ui_users", sa.Column("language", sa.String(length=2), nullable=False))

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_ui_users", "language")

    # Revert the version back in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc1' WHERE id = 1")
