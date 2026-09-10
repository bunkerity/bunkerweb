"""Upgrade to version 1.6.1-rc1

Revision ID: 8c096ca1beb8
Revises: f85e36780e55
Create Date: 2025-02-19 13:43:57.912879

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

# revision identifiers, used by Alembic.
revision: str = "8c096ca1beb8"
down_revision: Union[str, None] = "f85e36780e55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def add_constraint_if_the_data_allows(connection, table, constraint, statement):
    """Run one best-effort `ADD CONSTRAINT` inside its own SAVEPOINT.

    These three statements add constraints that 1.6 needs and that a 1.5.x schema never enforced, so
    legacy rows can refuse them: an orphaned `bw_jobs_cache.job_name`, two `bw_plugin_pages` rows for
    one plugin, two `bw_settings` rows sharing a `name` (legal before 1.6.0 -- `bw_settings` was
    `PRIMARY KEY (id, name)` + `UNIQUE (id)` there). That is why they were best-effort to begin with:
    until this revision they ran on a second connection whose every error was printed and dropped.

    Removing that second connection is what fixes the self-deadlock, but doing only that would turn a
    refused constraint into a failed upgrade -- PostgreSQL poisons the whole transaction on any error,
    and alembic runs the entire chain in ONE (`alembic/env.py:803-804`), so a single orphan row would
    roll back every revision and leave the scheduler unable to start. A SAVEPOINT keeps the original
    tolerance without the original connection: the failure rolls back to here, the outer transaction
    stays usable, and the chain goes on.

    A deliberate divergence from dev `d3f0244d1`, which removed the swallow along with the second
    connection. The database is left exactly as it was for that one constraint, which is what a 1.5.x
    database already lives with, and nothing later in the chain reads these constraints back: no later
    PostgreSQL revision names any of the three (the two that touch `bw_settings` constraints,
    `f29b02a768e8` and `d15ee0d0f93a`, both target `id`), there is no upsert on `bw_settings.name`
    anywhere in `src/common/db`, and `Plugins.pages` is a `Mapped[List[...]]` rather than a scalar, so
    a duplicate page row is read rather than raising.

    `SQLAlchemyError` and not `IntegrityError` is deliberate and measured: refusing the very same
    unique index surfaces as `IntegrityError` on PostgreSQL and SQLite but as `OperationalError` on
    MariaDB, and the helper this replaces caught everything. The cost of the wide catch is that a
    typo'd object name would also be swallowed, which the tests cover structurally instead.

    Offline (`alembic --sql`) is unchanged and still unsupported here: `op.get_bind()` is None in that
    mode, exactly as it already was for the `connection.execute` calls this revision has always made.
    """
    try:
        with connection.begin_nested():
            connection.execute(sa.text(statement))
    except SQLAlchemyError as error:
        print(
            f"⚠️ Could not add {constraint} on {table}: {type(error).__name__}. "
            f"Existing rows do not satisfy it; the upgrade continues without that constraint.",
            flush=True,
        )


def upgrade() -> None:
    # Get database connection
    connection = op.get_bind()

    # Use Alembic's transaction so earlier revisions cannot block a second connection.
    connection.execute(sa.text("ALTER TABLE bw_jobs DROP CONSTRAINT IF EXISTS bw_jobs_name_plugin_id_key"))

    # Check if constraint exists before adding it
    add_constraint_if_the_data_allows(
        connection,
        "bw_jobs_cache",
        "bw_jobs_cache_job_name_fkey",
        "DO $$ "
        "BEGIN "
        "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bw_jobs_cache_job_name_fkey') THEN "
        "    ALTER TABLE bw_jobs_cache ADD CONSTRAINT bw_jobs_cache_job_name_fkey "
        "    FOREIGN KEY (job_name) REFERENCES bw_jobs(name) ON UPDATE CASCADE ON DELETE CASCADE; "
        "  END IF; "
        "END $$;",
    )

    # Check if constraint exists before adding it
    add_constraint_if_the_data_allows(
        connection,
        "bw_plugin_pages",
        "bw_plugin_pages_plugin_id_key",
        "DO $$ "
        "BEGIN "
        "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bw_plugin_pages_plugin_id_key') THEN "
        "    ALTER TABLE bw_plugin_pages ADD CONSTRAINT bw_plugin_pages_plugin_id_key UNIQUE (plugin_id); "
        "  END IF; "
        "END $$;",
    )

    # Fresh 1.5.6-1.5.12 schemas lack the setting-name uniqueness required by 1.6.
    add_constraint_if_the_data_allows(
        connection,
        "bw_settings",
        "bw_settings_name_key",
        "DO $$ "
        "BEGIN "
        "  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'bw_settings'::regclass AND conname = 'bw_settings_name_key') THEN "
        "    ALTER TABLE bw_settings ADD CONSTRAINT bw_settings_name_key UNIQUE (name); "
        "  END IF; "
        "END $$;",
    )

    # Update the version in bw_metadata
    connection.execute(sa.text("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1"))


def downgrade() -> None:
    # Revert the version in bw_metadata
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1"))
