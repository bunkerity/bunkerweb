"""Upgrade to version 1.6.0-beta

Revision ID: 1e1fc017a424
Revises: 75a5d34f9a7d
Create Date: 2024-12-17 08:42:34.116054

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1e1fc017a424"
down_revision: Union[str, None] = "75a5d34f9a7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # --- Enums Changes ---
    # METHODS_ENUM now includes "wizard"
    # CUSTOM_CONFIGS_TYPES_ENUM now includes "default_server_stream", "crs_plugins_before", "crs_plugins_after"
    # PLUGIN_TYPES_ENUM now includes "ui"
    # INSTANCE_TYPE_ENUM and INSTANCE_STATUS_ENUM are new
    # These changes do not directly translate to SQLite schema changes since SQLite doesn't enforce enum types.
    # The application code will handle the new enum values. No direct DDL required for SQLite.

    # --- New Tables for UI ---
    op.create_table(
        "bw_ui_permissions",
        sa.Column("name", sa.String(64), primary_key=True),
    )

    op.create_table(
        "bw_ui_roles",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("description", sa.String(256), nullable=False),
        sa.Column("update_datetime", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "bw_ui_user_recovery_codes",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("code", sa.UnicodeText, nullable=False),
        sa.ForeignKeyConstraint(["user_name"], ["bw_ui_users.username"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.create_table(
        "bw_ui_roles_permissions",
        sa.Column("role_name", sa.String(64), nullable=False),
        sa.Column("permission_name", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["role_name"], ["bw_ui_roles.name"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_name"], ["bw_ui_permissions.name"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_name", "permission_name"),
    )

    op.create_table(
        "bw_ui_roles_users",
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("role_name", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["user_name"], ["bw_ui_users.username"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_name"], ["bw_ui_roles.name"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_name", "role_name"),
    )

    op.create_table(
        "bw_ui_user_sessions",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("ip", sa.String(39), nullable=False),
        sa.Column("user_agent", sa.TEXT, nullable=False),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_name"], ["bw_ui_users.username"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    from model import JSONText

    op.create_table(
        "bw_ui_user_columns_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("table_name", sa.Enum("bans", "configs", "instances", "jobs", "plugins", "reports", "services", name="tables_enum"), nullable=False),
        sa.Column("columns", JSONText, nullable=False),
        sa.ForeignKeyConstraint(["user_name"], ["bw_ui_users.username"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.UniqueConstraint("user_name", "table_name", name="uq_user_columns_preferences"),
    )

    # --- Templates Tables ---
    op.create_table(
        "bw_templates",
        sa.Column("id", sa.String(256), primary_key=True),
        sa.Column("name", sa.String(256), unique=True, nullable=False),
        sa.Column("plugin_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["bw_plugins.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.create_table(
        "bw_template_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.String(256), nullable=False, primary_key=True),
        sa.Column("title", sa.TEXT, nullable=False),
        sa.Column("subtitle", sa.TEXT, nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["bw_templates.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", "template_id"),
    )

    op.create_table(
        "bw_template_settings",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("template_id", sa.String(256), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("default", sa.TEXT, nullable=False),
        sa.Column("suffix", sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(["template_id"], ["bw_templates.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "setting_id", "step_id", "suffix"),
    )

    op.create_table(
        "bw_template_custom_configs",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("template_id", sa.String(256), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "http",
                "stream",
                "server_http",
                "server_stream",
                "default_server_http",
                "default_server_stream",
                "modsec",
                "modsec_crs",
                "crs_plugins_before",
                "crs_plugins_after",
                name="custom_configs_types_enum",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["bw_templates.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "step_id", "type", "name"),
    )

    # Create a new table with the updated custom_configs schema
    op.create_table(
        "bw_custom_configs_new",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("service_id", sa.String(64), sa.ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "http",
                "stream",
                "server_http",
                "server_stream",
                "default_server_http",
                "default_server_stream",
                "modsec",
                "modsec_crs",
                "crs_plugins_before",
                "crs_plugins_after",
                name="custom_configs_types_enum",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column(
            "method",
            sa.Enum(
                "ui",
                "scheduler",
                "autoconf",
                "manual",
                "wizard",
                name="methods_enum",
            ),
            nullable=False,
        ),
        sa.UniqueConstraint("service_id", "type", "name"),
    )

    # Copy data from the old table to the new table
    op.execute(
        """
        INSERT INTO bw_custom_configs_new (id, service_id, type, name, data, checksum, method)
        SELECT id, service_id, type, name, data, checksum, method FROM bw_custom_configs
        """
    )

    # Drop the old table
    op.drop_table("bw_custom_configs")

    # Rename the new table to match the original table's name
    op.rename_table("bw_custom_configs_new", "bw_custom_configs")

    # Create a new bw_settings table with updated schema (only 'id' as PK and 'name' as unique)
    op.create_table(
        "bw_settings_new",
        sa.Column("id", sa.String(256), primary_key=True),
        sa.Column("name", sa.String(256), unique=True, nullable=False),
        sa.Column("plugin_id", sa.String(64), sa.ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False),
        sa.Column("context", sa.Enum("global", "multisite", name="contexts_enum"), nullable=False),
        sa.Column("default", sa.TEXT, nullable=True),
        sa.Column("help", sa.String(512), nullable=False),
        sa.Column("label", sa.String(256), nullable=True),
        sa.Column("regex", sa.String(1024), nullable=False),
        sa.Column("type", sa.Enum("password", "text", "check", "select", name="settings_types_enum"), nullable=False),
        sa.Column("multiple", sa.String(128), nullable=True),
        sa.Column("order", sa.Integer, default=0, nullable=False),
    )

    # Copy data from the old table to the new table
    op.execute(
        """
        INSERT INTO bw_settings_new (id, name, plugin_id, context, "default", help, label, regex, type, multiple, "order")
        SELECT id, name, plugin_id, context, "default", help, label, regex, type, multiple, "order"
        FROM bw_settings
        """
    )

    # Drop the old table
    op.drop_table("bw_settings")

    # Rename the new table to match the original name
    op.rename_table("bw_settings_new", "bw_settings")

    # --- bw_jobs table changes ---
    # Add run_async column, drop success and last_run
    with op.batch_alter_table("bw_jobs") as batch_op:
        batch_op.add_column(sa.Column("run_async", sa.Boolean(), nullable=True, server_default="0"))
        # Remove old columns success, last_run
        batch_op.drop_column("success")
        batch_op.drop_column("last_run")
    # set run_async to not nullable now that we have a default
    op.execute("UPDATE bw_jobs SET run_async = 0 WHERE run_async IS NULL")
    with op.batch_alter_table("bw_jobs") as batch_op:
        batch_op.alter_column("run_async", nullable=False)

    # New bw_jobs_runs table
    op.create_table(
        "bw_jobs_runs",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("job_name", sa.String(128), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=True, server_default="0"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_name"], ["bw_jobs.name"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    # --- bw_services changes ---
    # Add creation_date, last_update
    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_update", sa.DateTime(timezone=True), nullable=True))

    # Set current timestamp for existing services
    op.execute("UPDATE bw_services SET creation_date = CURRENT_TIMESTAMP, last_update = CURRENT_TIMESTAMP")

    # Now make them non-nullable
    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.alter_column("creation_date", nullable=False)
        batch_op.alter_column("last_update", nullable=False)

    # --- bw_ui_users changes ---
    # Create a temporary new table
    op.create_table(
        "bw_ui_users_new",
        sa.Column("username", sa.String(256), primary_key=True),
        sa.Column("email", sa.String(256), nullable=True, unique=True),
        sa.Column("password", sa.String(60), nullable=False),
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False, server_default="manual"),
        sa.Column("admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("theme", sa.Enum("light", "dark", name="themes_enum"), nullable=False, server_default="light"),
        sa.Column("totp_secret", sa.String(256), nullable=True),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("update_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
    )

    # Migrate data from old bw_ui_users
    op.execute(
        """
        INSERT INTO bw_ui_users_new (username, password, method, admin, theme, creation_date, update_date)
        SELECT username, password, method, 1, 'light', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM bw_ui_users
        """
    )

    # Drop old table and rename new table
    op.drop_table("bw_ui_users")
    op.rename_table("bw_ui_users_new", "bw_ui_users")

    # --- bw_plugin_pages changes ---
    # Old had template_file, template_checksum, actions_file, actions_checksum, obfuscation_file, obfuscation_checksum
    # New has id, plugin_id(unique), data, checksum
    op.create_table(
        "bw_plugin_pages_new",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(64), nullable=False, unique=True),
        sa.Column("data", sa.LargeBinary(length=4294967295), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["bw_plugins.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_plugin_pages_new (id, plugin_id, data, checksum)
        SELECT id, plugin_id, template_file, '' FROM bw_plugin_pages
        """
    )

    op.drop_table("bw_plugin_pages")
    op.rename_table("bw_plugin_pages_new", "bw_plugin_pages")

    # --- bw_instances changes ---
    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(256), nullable=True))
        batch_op.add_column(sa.Column("type", sa.Enum("static", "container", "pod", name="instance_type_enum"), nullable=True))
        batch_op.add_column(sa.Column("status", sa.Enum("loading", "up", "down", name="instance_status_enum"), nullable=True))
        batch_op.add_column(sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=True))
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True))

    op.execute("DELETE FROM bw_instances WHERE name IS NULL")

    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.alter_column("name", nullable=False)
        batch_op.alter_column("type", nullable=False)
        batch_op.alter_column("status", nullable=False)
        batch_op.alter_column("method", nullable=False)
        batch_op.alter_column("creation_date", nullable=False)
        batch_op.alter_column("last_seen", nullable=False)

    # Update version to 1.6.0-beta
    op.execute("UPDATE bw_metadata SET version = '1.6.0-beta' WHERE id = 1")


def downgrade():
    # Downgrade steps: revert all changes that can't be easily undone.
    # This will drop newly created tables and attempt to restore old structure.

    # Drop new tables
    op.drop_table("bw_template_custom_configs")
    op.drop_table("bw_template_settings")
    op.drop_table("bw_template_steps")
    op.drop_table("bw_templates")
    op.drop_table("bw_jobs_runs")
    op.drop_table("bw_ui_user_sessions")
    op.drop_table("bw_ui_roles_users")
    op.drop_table("bw_ui_roles_permissions")
    op.drop_table("bw_ui_user_recovery_codes")
    op.drop_table("bw_ui_user_columns_preferences")
    op.drop_table("bw_ui_roles")
    op.drop_table("bw_ui_permissions")

    # Revert bw_plugin_pages
    op.create_table(
        "bw_plugin_pages_old",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(64), nullable=False),
        sa.Column("template_file", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("template_checksum", sa.String(128), nullable=False),
        sa.Column("actions_file", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("actions_checksum", sa.String(128), nullable=False),
        sa.Column("obfuscation_file", sa.LargeBinary(length=(2**32) - 1), nullable=True),
        sa.Column("obfuscation_checksum", sa.String(128), nullable=True),
        sa.ForeignKeyConstraint(["plugin_id"], ["bw_plugins.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )
    op.drop_table("bw_plugin_pages")
    op.rename_table("bw_plugin_pages_old", "bw_plugin_pages")

    # bw_jobs revert
    with op.batch_alter_table("bw_jobs") as batch_op:
        batch_op.add_column(sa.Column("success", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("last_run", sa.DateTime(), nullable=True))
        batch_op.drop_column("run_async")

    # bw_services revert
    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.drop_column("last_update")
        batch_op.drop_column("creation_date")

    # bw_instances revert
    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.drop_column("last_seen")
        batch_op.drop_column("creation_date")
        batch_op.drop_column("method")
        batch_op.drop_column("status")
        batch_op.drop_column("type")
        batch_op.drop_column("name")

    # Revert custom configs
    op.create_table(
        "bw_custom_configs_old",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("service_id", sa.String(64), sa.ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "http",
                "default_server_http",
                "server_http",
                "modsec",
                "modsec_crs",
                "stream",
                "server_stream",
                name="custom_configs_types_enum",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column(
            "method",
            sa.Enum(
                "ui",
                "scheduler",
                "autoconf",
                "manual",
                name="methods_enum",
            ),
            nullable=False,
        ),
        sa.UniqueConstraint("service_id", "type", "name"),
    )

    op.execute(
        """
        INSERT INTO bw_custom_configs_old (id, service_id, type, name, data, checksum, method)
        SELECT id, service_id, type, name, data, checksum, method
        FROM bw_custom_configs
        WHERE type IN ('http', 'default_server_http', 'server_http', 'modsec', 'modsec_crs', 'stream', 'server_stream')
        """
    )

    op.drop_table("bw_custom_configs")
    op.rename_table("bw_custom_configs_old", "bw_custom_configs")

    # Revert bw_settings
    op.create_table(
        "bw_settings_old",
        sa.Column("id", sa.String(256), primary_key=True),
        sa.Column("name", sa.String(256), primary_key=True),
        sa.Column("plugin_id", sa.String(64), sa.ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False),
        sa.Column("context", sa.Enum("global", "multisite", name="contexts_enum"), nullable=False),
        sa.Column("default", sa.String(4096), nullable=True, default=""),
        sa.Column("help", sa.String(512), nullable=False),
        sa.Column("label", sa.String(256), nullable=True),
        sa.Column("regex", sa.String(1024), nullable=False),
        sa.Column("type", sa.Enum("password", "text", "check", "select", name="settings_types_enum"), nullable=False),
        sa.Column("multiple", sa.String(128), nullable=True),
        sa.Column("order", sa.Integer, default=0, nullable=False),
        sa.PrimaryKeyConstraint("id", "name"),
        sa.UniqueConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO bw_settings_old (id, name, plugin_id, context, "default", help, label, regex, type, multiple, "order")
        SELECT id, name, plugin_id, context, "default", help, label, regex, type, multiple, "order"
        FROM bw_settings
        """
    )

    op.drop_table("bw_settings")
    op.rename_table("bw_settings_old", "bw_settings")

    # bw_ui_users revert
    op.create_table(
        "bw_ui_users_old",
        sa.Column("id", sa.Integer, primary_key=True, default=1),
        sa.Column("username", sa.String(256), nullable=False, unique=True),
        sa.Column("password", sa.String(60), nullable=False),
        sa.Column("is_two_factor_enabled", sa.Boolean, nullable=False, default=False),
        sa.Column("secret_token", sa.String(32), nullable=True, unique=True, default=None),
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum"), nullable=False, default="manual"),
    )

    op.execute(
        """
        INSERT INTO bw_ui_users_old (username, password, method)
        SELECT username, password, method FROM bw_ui_users
        """
    )

    op.drop_table("bw_ui_users")
    op.rename_table("bw_ui_users_old", "bw_ui_users")

    # Revert version
    op.execute("UPDATE bw_metadata SET version = '1.5.12' WHERE id = 1")
