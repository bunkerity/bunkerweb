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


def execute_with_new_transaction(connection, statement):
    """Execute SQL statement in a separate transaction."""
    try:
        # Create a new connection from the engine
        engine = connection.engine
        with engine.begin() as new_connection:
            new_connection.execute(statement)
    except Exception as e:
        print(f"Ignoring error: {e}", flush=True)


def upgrade() -> None:
    # Get database connection
    connection = op.get_bind()

    # Execute each operation with its own transaction
    execute_with_new_transaction(connection, sa.text("ALTER TABLE bw_jobs DROP CONSTRAINT IF EXISTS bw_jobs_name_plugin_id_key"))

    # Check if constraint exists before adding it
    execute_with_new_transaction(
        connection,
        sa.text(
            "DO $$ "
            "BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bw_jobs_cache_job_name_fkey') THEN "
            "    ALTER TABLE bw_jobs_cache ADD CONSTRAINT bw_jobs_cache_job_name_fkey "
            "    FOREIGN KEY (job_name) REFERENCES bw_jobs(name) ON UPDATE CASCADE ON DELETE CASCADE; "
            "  END IF; "
            "END $$;"
        ),
    )

    # Check if constraint exists before adding it
    execute_with_new_transaction(
        connection,
        sa.text(
            "DO $$ "
            "BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bw_plugin_pages_plugin_id_key') THEN "
            "    ALTER TABLE bw_plugin_pages ADD CONSTRAINT bw_plugin_pages_plugin_id_key UNIQUE (plugin_id); "
            "  END IF; "
            "END $$;"
        ),
    )

    # Update the version in bw_metadata
    execute_with_new_transaction(connection, sa.text("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1"))


def downgrade() -> None:
    # Revert the version in bw_metadata
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1"))
