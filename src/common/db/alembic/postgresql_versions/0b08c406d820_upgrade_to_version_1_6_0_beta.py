"""Upgrade to version 1.6.0-beta

Revision ID: 0b08c406d820
Revises: fbd680c6ffeb
Create Date: 2024-12-19 14:47:13.427196

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0b08c406d820"
down_revision: Union[str, None] = "fbd680c6ffeb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Use create_type=False since these enums already exist
    old_methods_enum = postgresql.ENUM("ui", "scheduler", "autoconf", "manual", name="methods_enum", create_type=False)
    new_methods_enum = postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False)

    old_cct_enum = postgresql.ENUM(
        "http", "stream", "server_http", "server_stream", "default_server_http", "modsec", "modsec_crs", name="custom_configs_types_enum", create_type=False
    )
    new_cct_enum = postgresql.ENUM(
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
        create_type=False,
    )

    old_pt_enum = postgresql.ENUM("core", "external", "pro", name="plugin_types_enum", create_type=False)
    new_pt_enum = postgresql.ENUM("core", "external", "ui", "pro", name="plugin_types_enum", create_type=False)

    # Add new enum values if not already present
    op.execute("ALTER TYPE custom_configs_types_enum ADD VALUE IF NOT EXISTS 'default_server_stream'")
    op.execute("ALTER TYPE custom_configs_types_enum ADD VALUE IF NOT EXISTS 'crs_plugins_before'")
    op.execute("ALTER TYPE custom_configs_types_enum ADD VALUE IF NOT EXISTS 'crs_plugins_after'")

    op.execute("ALTER TYPE plugin_types_enum ADD VALUE IF NOT EXISTS 'ui'")

    # Alter columns that rely on these enums
    op.alter_column("bw_plugins", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False, existing_server_default="manual")
    op.alter_column("bw_services", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False)
    op.alter_column("bw_custom_configs", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False)
    op.alter_column("bw_ui_users", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False, existing_server_default="manual")

    op.alter_column("bw_custom_configs", "type", existing_type=old_cct_enum, type_=new_cct_enum, existing_nullable=False)
    op.alter_column("bw_plugins", "type", existing_type=old_pt_enum, type_=new_pt_enum, existing_nullable=False, existing_server_default="core")

    # Create new UI tables
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

    tables_enum = postgresql.ENUM("bans", "configs", "instances", "jobs", "plugins", "reports", "services", name="tables_enum", create_type=False)

    op.execute("CREATE TYPE tables_enum AS ENUM ('bans', 'configs', 'instances', 'jobs', 'plugins', 'reports', 'services')")

    op.create_table(
        "bw_ui_user_columns_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("table_name", tables_enum, nullable=False),
        sa.Column("columns", JSONText, nullable=False),
        sa.ForeignKeyConstraint(["user_name"], ["bw_ui_users.username"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.UniqueConstraint("user_name", "table_name", name="uq_user_columns_preferences"),
    )

    # Templates tables
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
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("subtitle", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["bw_templates.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", "template_id"),
    )

    op.create_table(
        "bw_template_settings",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("template_id", sa.String(256), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("default", sa.Text, nullable=False),
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
        sa.Column("type", new_cct_enum, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["bw_templates.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "step_id", "type", "name"),
    )

    # bw_jobs changes (add run_async, remove success and last_run)
    with op.batch_alter_table("bw_jobs") as batch_op:
        batch_op.add_column(sa.Column("run_async", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.drop_column("success")
        batch_op.drop_column("last_run")

    op.create_table(
        "bw_jobs_runs",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("job_name", sa.String(128), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=True, server_default="0"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["job_name"], ["bw_jobs.name"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    # bw_services add creation_date, last_update
    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch_op.add_column(sa.Column("last_update", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")))

    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.alter_column("creation_date", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("last_update", existing_type=sa.DateTime(timezone=True), nullable=False)

    # bw_ui_users changes
    themes_enum = postgresql.ENUM("light", "dark", name="themes_enum", create_type=False)

    op.execute("CREATE TYPE themes_enum AS ENUM ('light', 'dark')")

    with op.batch_alter_table("bw_ui_users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(256), nullable=True, unique=True))
        batch_op.add_column(sa.Column("admin", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("theme", themes_enum, nullable=False, server_default="light"))
        batch_op.add_column(sa.Column("totp_secret", sa.String(256), nullable=True))
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch_op.add_column(sa.Column("update_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch_op.drop_column("is_two_factor_enabled")
        batch_op.drop_column("secret_token")

    op.execute("UPDATE bw_ui_users SET admin=TRUE, theme='light', creation_date=CURRENT_TIMESTAMP, update_date=CURRENT_TIMESTAMP")

    # bw_plugin_pages changes
    with op.batch_alter_table("bw_plugin_pages") as batch_op:
        batch_op.add_column(sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False))
        batch_op.add_column(sa.Column("checksum", sa.String(128), nullable=False))

    op.execute(
        """
        UPDATE bw_plugin_pages
        SET data = template_file, checksum = template_checksum
        WHERE template_file IS NOT NULL
        """
    )

    with op.batch_alter_table("bw_plugin_pages") as batch_op:
        batch_op.drop_column("template_file")
        batch_op.drop_column("template_checksum")
        batch_op.drop_column("actions_file")
        batch_op.drop_column("actions_checksum")
        batch_op.drop_column("obfuscation_file")
        batch_op.drop_column("obfuscation_checksum")

    # bw_instances changes
    old_methods_enum_for_instances = postgresql.ENUM("ui", "scheduler", "autoconf", "manual", name="methods_enum", create_type=False)

    # Add new enum values for instances if needed before altering columns
    op.execute("ALTER TYPE methods_enum ADD VALUE IF NOT EXISTS 'wizard'")

    new_it_enum = postgresql.ENUM("static", "container", "pod", name="instance_type_enum", create_type=False)
    new_is_enum = postgresql.ENUM("loading", "up", "down", name="instance_status_enum", create_type=False)

    op.execute("CREATE TYPE instance_type_enum AS ENUM ('static', 'container', 'pod')")
    op.execute("CREATE TYPE instance_status_enum AS ENUM ('loading', 'up', 'down')")

    extended_methods_enum = postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False)

    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(256), nullable=True))
        batch_op.add_column(sa.Column("type", new_it_enum, nullable=True))
        batch_op.add_column(sa.Column("status", new_it_enum, nullable=True))
        batch_op.add_column(sa.Column("method", old_methods_enum_for_instances, nullable=True))
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch_op.add_column(sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")))

    op.execute("DELETE FROM bw_instances WHERE name IS NULL")

    op.alter_column(
        "bw_instances",
        "method",
        existing_type=old_methods_enum_for_instances,
        type_=extended_methods_enum,
        existing_nullable=False,
        existing_server_default="manual",
    )

    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.alter_column("name", existing_type=sa.String(256), nullable=False)
        batch_op.alter_column("type", existing_type=new_it_enum, nullable=False)
        batch_op.alter_column("status", existing_type=new_is_enum, nullable=False)
        batch_op.alter_column("method", existing_type=extended_methods_enum, nullable=False)
        batch_op.alter_column("creation_date", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("last_seen", existing_type=sa.DateTime(timezone=True), nullable=False)

    # Update version
    op.execute("UPDATE bw_metadata SET version = '1.6.0-beta' WHERE id = 1")


def downgrade():
    # Reverse changes:
    # 1. Drop added columns from bw_instances
    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.drop_column("last_seen")
        batch_op.drop_column("creation_date")
        batch_op.drop_column("method")
        batch_op.drop_column("status")
        batch_op.drop_column("type")
        batch_op.drop_column("name")

    # 2. Revert bw_plugin_pages to old structure
    op.create_table(
        "bw_plugin_pages_old",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(64), nullable=False),
        sa.Column("template_file", sa.LargeBinary(length=(2**32)), nullable=False),
        sa.Column("template_checksum", sa.String(128), nullable=False),
        sa.Column("actions_file", sa.LargeBinary(length=(2**32)), nullable=False),
        sa.Column("actions_checksum", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["bw_plugins.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_plugin_pages_old (id, plugin_id, template_file, template_checksum, actions_file, actions_checksum)
        SELECT id, plugin_id, NULL, '', NULL, ''
        FROM bw_plugin_pages
        """
    )

    op.drop_table("bw_plugin_pages")
    op.rename_table("bw_plugin_pages_old", "bw_plugin_pages")

    # 3. Revert bw_ui_users to old structure
    op.create_table(
        "bw_ui_users_old",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(256), nullable=False, unique=True),
        sa.Column("password", sa.String(60), nullable=False),
        sa.Column("is_two_factor_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("secret_token", sa.String(32), nullable=True, unique=True, default=None),
        sa.Column("method", sa.String(16), nullable=False, server_default="manual"),
    )

    op.execute(
        """
        INSERT INTO bw_ui_users_old (id, username, password, is_two_factor_enabled, secret_token, method)
        SELECT 1, username, password, '0', NULL, 'manual'
        FROM bw_ui_users
        """
    )

    op.drop_table("bw_ui_users")
    op.rename_table("bw_ui_users_old", "bw_ui_users")

    # 4. Drop new UI and templates tables
    op.drop_table("bw_template_custom_configs")
    op.drop_table("bw_template_settings")
    op.drop_table("bw_template_steps")
    op.drop_table("bw_templates")
    op.drop_table("bw_ui_user_columns_preferences")
    op.drop_table("bw_ui_user_sessions")
    op.drop_table("bw_ui_roles_users")
    op.drop_table("bw_ui_roles_permissions")
    op.drop_table("bw_ui_user_recovery_codes")
    op.drop_table("bw_ui_roles")
    op.drop_table("bw_ui_permissions")

    # 5. Drop new enums
    op.execute("DROP TYPE IF EXISTS themes_enum")
    op.execute("DROP TYPE IF EXISTS tables_enum")
    op.execute("DROP TYPE IF EXISTS instance_status_enum")

    # 6. Drop new enum values
    op.execute("ALTER TYPE methods_enum DROP VALUE IF EXISTS 'wizard'")
    op.execute("ALTER TYPE custom_configs_types_enum DROP VALUE IF EXISTS 'default_server_stream'")
    op.execute("ALTER TYPE custom_configs_types_enum DROP VALUE IF EXISTS 'crs_plugins_before'")
    op.execute("ALTER TYPE custom_configs_types_enum DROP VALUE IF EXISTS 'crs_plugins_after'")
    op.execute("ALTER TYPE plugin_types_enum DROP VALUE IF EXISTS 'ui'")

    # 7. Revert version
    op.execute("UPDATE bw_metadata SET version = '1.5.12' WHERE id = 1")
