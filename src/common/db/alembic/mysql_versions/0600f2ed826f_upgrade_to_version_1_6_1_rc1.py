"""Upgrade to version 1.6.1-rc1

Revision ID: 0600f2ed826f
Revises: 9f917f5e76b3
Create Date: 2025-02-19 13:38:02.653796

"""

from contextlib import suppress
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "0600f2ed826f"
down_revision: Union[str, None] = "9f917f5e76b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with suppress(Exception):
        op.create_unique_constraint(None, "bw_plugin_pages", ["plugin_id"])

    with suppress(Exception):
        op.drop_index("id", table_name="bw_settings")

    with suppress(Exception):
        op.create_unique_constraint(None, "bw_settings", ["name"])

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1")
