"""Upgrade to version 1.6.0-beta

Revision ID: 839424d81cf7
Revises: 3d6af0bf1bec
Create Date: 2024-12-19 13:34:03.714317

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "839424d81cf7"
down_revision: Union[str, None] = "3d6af0bf1bec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Define old and new ENUMs for methods_enum (adding "wizard")
    old_methods_enum = sa.Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum")
    new_methods_enum = sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum")

    # Alter columns that use methods_enum
    op.alter_column("bw_plugins", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False, existing_server_default="manual")

    op.alter_column("bw_services", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False)

    op.alter_column("bw_custom_configs", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False)

    op.alter_column("bw_ui_users", "method", existing_type=old_methods_enum, type_=new_methods_enum, existing_nullable=False, existing_server_default="manual")

    # Update custom_configs_types_enum (adding "default_server_stream", "crs_plugins_before", "crs_plugins_after")
    old_cct_enum = sa.Enum("http", "stream", "server_http", "server_stream", "default_server_http", "modsec", "modsec_crs", name="custom_configs_types_enum")
    new_cct_enum = sa.Enum(
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
    )

    op.alter_column("bw_custom_configs", "type", existing_type=old_cct_enum, type_=new_cct_enum, existing_nullable=False)

    # Update plugin_types_enum (adding "ui")
    old_pt_enum = sa.Enum("core", "external", "pro", name="plugin_types_enum")
    new_pt_enum = sa.Enum("core", "external", "ui", "pro", name="plugin_types_enum")

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

    op.create_table(
        "bw_ui_user_columns_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("table_name", sa.Enum("bans", "configs", "instances", "jobs", "plugins", "reports", "services", name="tables_enum"), nullable=False),
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
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_name"], ["bw_jobs.name"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    # bw_services add creation_date, last_update
    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_update", sa.DateTime(timezone=True), nullable=True))

    # Set current timestamp for existing services data
    op.execute("UPDATE bw_services SET creation_date = CURRENT_TIMESTAMP, last_update = CURRENT_TIMESTAMP")

    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.alter_column("creation_date", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("last_update", existing_type=sa.DateTime(timezone=True), nullable=False)

    # bw_ui_users changes
    with op.batch_alter_table("bw_ui_users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(256), nullable=True, unique=True))
        batch_op.add_column(sa.Column("admin", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("theme", sa.Enum("light", "dark", name="themes_enum"), nullable=False, server_default="light"))
        batch_op.add_column(sa.Column("totp_secret", sa.String(256), nullable=True))
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()))
        batch_op.add_column(sa.Column("update_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()))
        batch_op.drop_column("is_two_factor_enabled")
        batch_op.drop_column("secret_token")

    # Set defaults for existing bw_ui_users rows
    op.execute("UPDATE bw_ui_users SET admin=1, theme='light', creation_date=CURRENT_TIMESTAMP, update_date=CURRENT_TIMESTAMP")

    # bw_plugin_pages changes
    with op.batch_alter_table("bw_plugin_pages") as batch_op:
        batch_op.add_column(sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False))
        batch_op.add_column(sa.Column("checksum", sa.String(128), nullable=False))

    # Add old data to new columns
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
    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(256), nullable=True))
        # Add the 'type' column with the old enum definition (or no enum yet if it didn’t exist before)
        # For instance, if previously there was no enum, start with the initial values:
        old_it_enum = sa.Enum("static", name="instance_type_enum")  # The original value set
        batch_op.add_column(sa.Column("type", old_it_enum, nullable=True))
        # Similarly add the 'status', 'method', 'creation_date', 'last_seen' columns
        old_is_enum = sa.Enum("loading", "up", name="instance_status_enum")
        batch_op.add_column(sa.Column("status", old_is_enum, nullable=True))

        old_methods_enum = sa.Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum")
        batch_op.add_column(sa.Column("method", old_methods_enum, nullable=True))

        batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True))

    op.execute("DELETE FROM bw_instances WHERE name IS NULL")

    # Now that columns exist and have values, alter their definitions if needed:
    new_it_enum = sa.Enum("static", "container", "pod", name="instance_type_enum")
    op.alter_column("bw_instances", "type", existing_type=old_it_enum, type_=new_it_enum, existing_nullable=False, existing_server_default="static")

    new_is_enum = sa.Enum("loading", "up", "down", name="instance_status_enum")
    op.alter_column("bw_instances", "status", existing_type=old_is_enum, type_=new_is_enum, existing_nullable=False, existing_server_default="loading")

    # Similarly alter the method column to the new enum with 'wizard' if needed:
    extended_methods_enum = sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum")
    op.alter_column(
        "bw_instances", "method", existing_type=old_methods_enum, type_=extended_methods_enum, existing_nullable=False, existing_server_default="manual"
    )

    # Finally, now set them to NOT NULL
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
    # Revert enums to their old definitions by altering columns back
    old_methods_enum = sa.Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum")
    # methods_enum had "wizard" added, now remove it
    op.alter_column(
        "bw_plugins",
        "method",
        existing_type=sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"),
        type_=old_methods_enum,
        existing_nullable=False,
        existing_server_default="manual",
    )

    op.alter_column(
        "bw_services",
        "method",
        existing_type=sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"),
        type_=old_methods_enum,
        existing_nullable=False,
    )

    op.alter_column(
        "bw_custom_configs",
        "method",
        existing_type=sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"),
        type_=old_methods_enum,
        existing_nullable=False,
    )

    op.alter_column(
        "bw_ui_users",
        "method",
        existing_type=sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"),
        type_=old_methods_enum,
        existing_nullable=False,
        existing_server_default="manual",
    )

    # custom_configs_types_enum remove "default_server_stream", "crs_plugins_before", "crs_plugins_after"
    old_cct_enum = sa.Enum("http", "default_server_http", "server_http", "modsec", "modsec_crs", "stream", "server_stream", name="custom_configs_types_enum")
    op.alter_column(
        "bw_custom_configs",
        "type",
        existing_type=sa.Enum(
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
        type_=old_cct_enum,
        existing_nullable=False,
    )

    # plugin_types_enum remove "ui"
    old_pt_enum = sa.Enum("core", "external", "pro", name="plugin_types_enum")
    op.alter_column(
        "bw_plugins",
        "type",
        existing_type=sa.Enum("core", "external", "ui", "pro", name="plugin_types_enum"),
        type_=old_pt_enum,
        existing_nullable=False,
        existing_server_default="core",
    )

    # instance_type_enum revert to just "static"
    old_it_enum = sa.Enum("static", name="instance_type_enum")
    op.alter_column(
        "bw_instances",
        "type",
        existing_type=sa.Enum("static", "container", "pod", name="instance_type_enum"),
        type_=old_it_enum,
        existing_nullable=False,
        existing_server_default="static",
    )

    # instance_status_enum revert to "loading", "up"
    old_is_enum = sa.Enum("loading", "up", name="instance_status_enum")
    op.alter_column(
        "bw_instances",
        "status",
        existing_type=sa.Enum("loading", "up", "down", name="instance_status_enum"),
        type_=old_is_enum,
        existing_nullable=False,
        existing_server_default="loading",
    )

    # Drop newly created UI and templates tables
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

    # Revert bw_settings constraints: old primary key was (id,name) and there was a unique constraint on id
    op.drop_constraint("bw_settings_name_key", "bw_settings", type_="unique")
    op.drop_constraint("bw_settings_pkey", "bw_settings", type_="primary")

    # Recreate old constraints:
    # PrimaryKeyConstraint("id", "name"), UniqueConstraint("id")
    # Note: The original primary key and unique constraints must be re-added as they were initially.
    op.create_primary_key("bw_settings_pkey", "bw_settings", ["id", "name"])
    op.create_unique_constraint("id", "bw_settings", ["id"])

    # bw_jobs revert: drop run_async, add success and last_run
    with op.batch_alter_table("bw_jobs") as batch_op:
        batch_op.drop_column("run_async")
        batch_op.add_column(sa.Column("success", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("last_run", sa.DateTime(), nullable=True))

    # Drop bw_jobs_runs table
    op.drop_table("bw_jobs_runs")

    # bw_services revert: remove creation_date, last_update
    with op.batch_alter_table("bw_services") as batch_op:
        batch_op.drop_column("last_update")
        batch_op.drop_column("creation_date")

    # bw_ui_users revert: drop email, admin, theme, totp_secret, creation_date, update_date
    # add back is_two_factor_enabled, secret_token
    with op.batch_alter_table("bw_ui_users") as batch_op:
        batch_op.drop_column("email")
        batch_op.drop_column("admin")
        batch_op.drop_column("theme")
        batch_op.drop_column("totp_secret")
        batch_op.drop_column("creation_date")
        batch_op.drop_column("update_date")
        batch_op.add_column(sa.Column("is_two_factor_enabled", sa.Boolean, nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("secret_token", sa.String(32), nullable=True, unique=True, default=None))

    # bw_plugin_pages revert: remove data, checksum, add template_file, template_checksum, actions_file, actions_checksum, obfuscation_file, obfuscation_checksum
    with op.batch_alter_table("bw_plugin_pages") as batch_op:
        batch_op.drop_column("data")
        batch_op.drop_column("checksum")
        batch_op.add_column(sa.Column("template_file", sa.LargeBinary(length=(2**32) - 1), nullable=False))
        batch_op.add_column(sa.Column("template_checksum", sa.String(128), nullable=False))
        batch_op.add_column(sa.Column("actions_file", sa.LargeBinary(length=(2**32) - 1), nullable=False))
        batch_op.add_column(sa.Column("actions_checksum", sa.String(128), nullable=False))
        batch_op.add_column(sa.Column("obfuscation_file", sa.LargeBinary(length=(2**32) - 1), nullable=True))
        batch_op.add_column(sa.Column("obfuscation_checksum", sa.String(128), nullable=True))

    # bw_instances revert: drop name, type, status, method, creation_date, last_seen
    with op.batch_alter_table("bw_instances") as batch_op:
        batch_op.drop_column("last_seen")
        batch_op.drop_column("creation_date")
        batch_op.drop_column("method")
        batch_op.drop_column("status")
        batch_op.drop_column("type")
        batch_op.drop_column("name")

    # Revert version
    op.execute("UPDATE bw_metadata SET version = '1.5.12' WHERE id = 1")
