"""Upgrade to version 1.6.1-rc1

Revision ID: 8c096ca1beb8
Revises: f85e36780e55
Create Date: 2025-02-19 13:43:57.912879

"""

from contextlib import suppress
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8c096ca1beb8"
down_revision: Union[str, None] = "f85e36780e55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get database connection
    connection = op.get_bind()

    # Execute each operation with its own exception handling
    with suppress(Exception):
        connection.execute(sa.text("ALTER TABLE bw_jobs DROP CONSTRAINT IF EXISTS bw_jobs_name_plugin_id_key"))

    with suppress(Exception):
        connection.execute(
            sa.text(
                "ALTER TABLE bw_jobs_cache ADD CONSTRAINT bw_jobs_cache_job_name_fkey "
                "FOREIGN KEY (job_name) REFERENCES bw_jobs(name) ON UPDATE CASCADE ON DELETE CASCADE"
            )
        )

    with suppress(Exception):
        connection.execute(sa.text("ALTER TABLE bw_plugin_pages ADD CONSTRAINT bw_plugin_pages_plugin_id_key UNIQUE (plugin_id)"))

    # Update the version in bw_metadata
    connection.execute(sa.text("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1"))


def downgrade() -> None:
    # Revert the version in bw_metadata
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1"))
