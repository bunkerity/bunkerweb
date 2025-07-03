"""Upgrade to version 1.6.2-rc2

Revision ID: 4e98a08c5902
Revises: 50233e485cc2
Create Date: 2025-04-23 18:32:24.455097

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e98a08c5902"
down_revision: Union[str, None] = "50233e485cc2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_ui_users", sa.Column("language", sa.String(length=2), nullable=False, server_default="en"))

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_ui_users", "language")

    # Revert the version back in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc1' WHERE id = 1")
