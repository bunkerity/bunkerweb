"""Upgrade to version 1.6.1-rc1

Revision ID: 8c096ca1beb8
Revises: f85e36780e55
Create Date: 2025-02-19 13:43:57.912879

"""

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

    # Use Alembic's transaction so earlier revisions cannot block a second connection.
    connection.execute(sa.text("ALTER TABLE bw_jobs DROP CONSTRAINT IF EXISTS bw_jobs_name_plugin_id_key"))

    # Check if constraint exists before adding it
    connection.execute(
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
    connection.execute(
        sa.text(
            "DO $$ "
            "BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bw_plugin_pages_plugin_id_key') THEN "
            "    ALTER TABLE bw_plugin_pages ADD CONSTRAINT bw_plugin_pages_plugin_id_key UNIQUE (plugin_id); "
            "  END IF; "
            "END $$;"
        ),
    )

    # Fresh 1.5.6-1.5.12 schemas lack the setting-name uniqueness required by 1.6.
    connection.execute(
        sa.text(
            "DO $$ "
            "BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'bw_settings'::regclass AND conname = 'bw_settings_name_key') THEN "
            "    ALTER TABLE bw_settings ADD CONSTRAINT bw_settings_name_key UNIQUE (name); "
            "  END IF; "
            "END $$;"
        ),
    )

    # Update the version in bw_metadata
    connection.execute(sa.text("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1"))


def downgrade() -> None:
    # Revert the version in bw_metadata
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1"))
