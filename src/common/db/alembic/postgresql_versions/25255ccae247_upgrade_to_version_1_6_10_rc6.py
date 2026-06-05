"""Upgrade to version 1.6.10~rc6

Revision ID: 25255ccae247
Revises: d15ff778dbeb
Create Date: 2026-05-07 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25255ccae247"
down_revision: Union[str, None] = "d15ff778dbeb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, index_name, [columns]) — single-column B-tree indexes added in rc6 to
# fix slow-log full table scans reported in https://github.com/bunkerity/bunkerweb/issues/3368
INDEX_TARGETS = [
    ("bw_plugins", "ix_bw_plugins_config_changed", ["config_changed"]),
    ("bw_settings", "ix_bw_settings_plugin_id", ["plugin_id"]),
    ("bw_selects", "ix_bw_selects_setting_id", ["setting_id"]),
    ("bw_multiselects", "ix_bw_multiselects_setting_id", ["setting_id"]),
    ("bw_services", "ix_bw_services_is_draft", ["is_draft"]),
    ("bw_services_settings", "ix_bw_services_settings_setting_id", ["setting_id"]),
    ("bw_jobs", "ix_bw_jobs_plugin_id", ["plugin_id"]),
    ("bw_jobs_cache", "ix_bw_jobs_cache_job_name", ["job_name"]),
    ("bw_jobs_cache", "ix_bw_jobs_cache_service_id", ["service_id"]),
    ("bw_jobs_runs", "ix_bw_jobs_runs_job_name", ["job_name"]),
    ("bw_templates", "ix_bw_templates_plugin_id", ["plugin_id"]),
    ("bw_template_settings", "ix_bw_template_settings_setting_id", ["setting_id"]),
    ("bw_ui_users", "ix_bw_ui_users_admin", ["admin"]),
    ("bw_ui_user_sessions", "ix_bw_ui_user_sessions_user_name", ["user_name"]),
    ("bw_ui_user_recovery_codes", "ix_bw_ui_user_recovery_codes_user_name", ["user_name"]),
    ("bw_ui_roles_users", "ix_bw_ui_roles_users_role_name", ["role_name"]),
    ("bw_ui_roles_permissions", "ix_bw_ui_roles_permissions_permission_name", ["permission_name"]),
    ("bw_api_user_permissions", "ix_bw_api_user_permissions_api_user", ["api_user"]),
]


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc6' WHERE id = 1")

    # PostgreSQL does NOT auto-create FK indexes (unlike MySQL/MariaDB), so
    # every CASCADE FK in INDEX_TARGETS is guaranteed missing on existing
    # installs. CREATE INDEX CONCURRENTLY runs without taking a write lock on
    # the table so the upgrade is safe on live systems — but it cannot run
    # inside a transaction, hence the autocommit_block.
    with op.get_context().autocommit_block():
        for table_name, index_name, columns in INDEX_TARGETS:
            cols_sql = ", ".join(f'"{c}"' for c in columns)
            op.execute(f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" ON "{table_name}" ({cols_sql})')


def downgrade() -> None:
    # DROP INDEX CONCURRENTLY also requires running outside a transaction.
    with op.get_context().autocommit_block():
        for _, index_name, _ in reversed(INDEX_TARGETS):
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{index_name}"')

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc5' WHERE id = 1")
