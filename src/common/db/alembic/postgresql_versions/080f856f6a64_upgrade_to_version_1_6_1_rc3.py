"""Upgrade to version 1.6.1-rc3

Revision ID: 080f856f6a64
Revises: 7a0181395802
Create Date: 2025-03-03 15:15:14.245348

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "080f856f6a64"
down_revision: Union[str, None] = "7a0181395802"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "bw_ui_user_columns_preferences",
        "table_name",
        existing_type=postgresql.ENUM("bans", "configs", "instances", "jobs", "plugins", "reports", "services", name="tables_enum"),
        type_=sa.String(length=256),
        existing_nullable=False,
    )

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc3' WHERE id = 1")


def downgrade() -> None:
    op.alter_column(
        "bw_ui_user_columns_preferences",
        "table_name",
        existing_type=sa.String(length=256),
        type_=postgresql.ENUM("bans", "configs", "instances", "jobs", "plugins", "reports", "services", name="tables_enum"),
        existing_nullable=False,
    )

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc2' WHERE id = 1")
