"""Upgrade to version 1.6.10~rc6

Revision ID: dcd7a1448119
Revises: 4a16ae77a27b
Create Date: 2026-05-07 10:29:07.989569

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "dcd7a1448119"
down_revision: Union[str, None] = "4a16ae77a27b"
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


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text("""
                SELECT 1
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                  AND index_name = :index_name
                LIMIT 1
                """),
            {"table_name": table_name, "index_name": index_name},
        ).scalar()
    )


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc6' WHERE id = 1")

    conn = op.get_bind()

    for table_name, index_name, columns in INDEX_TARGETS:
        if not _index_exists(conn, table_name, index_name):
            op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.10~rc5' WHERE id = 1")

    conn = op.get_bind()

    for table_name, index_name, _ in reversed(INDEX_TARGETS):
        if _index_exists(conn, table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
