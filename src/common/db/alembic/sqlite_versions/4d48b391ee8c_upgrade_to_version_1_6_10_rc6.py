"""Upgrade to version 1.6.10~rc6

Revision ID: 4d48b391ee8c
Revises: 9c5dcacc541a
Create Date: 2026-05-07 10:28:42.724509

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d48b391ee8c"
down_revision: Union[str, None] = "9c5dcacc541a"
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

    # SQLite has native CREATE INDEX IF NOT EXISTS, so no information-schema
    # helper is needed. PostgreSQL/SQLite do not auto-create FK indexes, so
    # every CASCADE FK in INDEX_TARGETS is guaranteed missing on existing
    # installs.
    for table_name, index_name, columns in INDEX_TARGETS:
        cols_sql = ", ".join(f'"{c}"' for c in columns)
        op.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ({cols_sql})')


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc5' WHERE id = 1")

    for _, index_name, _ in reversed(INDEX_TARGETS):
        op.execute(f'DROP INDEX IF EXISTS "{index_name}"')
