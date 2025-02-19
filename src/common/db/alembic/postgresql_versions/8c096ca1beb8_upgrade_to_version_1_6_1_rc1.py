"""Upgrade to version 1.6.1-rc1

Revision ID: 8c096ca1beb8
Revises: f85e36780e55
Create Date: 2025-02-19 13:43:57.912879

"""

from contextlib import suppress
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c096ca1beb8"
down_revision: Union[str, None] = "f85e36780e55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with suppress(Exception):
        op.drop_constraint("bw_jobs_name_plugin_id_key", "bw_jobs", type_="unique")

    with suppress(Exception):
        op.create_foreign_key(None, "bw_jobs_cache", "bw_jobs", ["job_name"], ["name"], onupdate="cascade", ondelete="cascade")

    with suppress(Exception):
        op.create_unique_constraint(None, "bw_plugin_pages", ["plugin_id"])

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1")
