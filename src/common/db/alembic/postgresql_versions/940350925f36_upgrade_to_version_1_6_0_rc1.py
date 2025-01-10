"""Upgrade to version 1.6.0-rc1

Revision ID: 940350925f36
Revises: 0b08c406d820
Create Date: 2024-12-20 11:02:59.703530

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "940350925f36"
down_revision: Union[str, None] = "0b08c406d820"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop foreign keys referencing bw_services
    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.drop_constraint("bw_custom_configs_service_id_fkey", type_="foreignkey")
    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.drop_constraint("bw_services_settings_service_id_fkey", type_="foreignkey")
    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.drop_constraint("bw_jobs_cache_service_id_fkey", type_="foreignkey")

    # Create the new bw_services table with updated schema
    op.create_table(
        "bw_services_new",
        sa.Column("id", sa.String(256), primary_key=True),
        sa.Column("method", postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False), nullable=False),
        sa.Column("is_draft", sa.Boolean, default=False, nullable=False),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=False),
    )

    # Copy data from old bw_services to bw_services_new
    op.execute(
        """
        INSERT INTO bw_services_new (id, method, is_draft, creation_date, last_update)
        SELECT id, method, is_draft, creation_date, last_update
        FROM bw_services
    """
    )

    # Drop old bw_services table now that foreign keys are removed
    op.drop_table("bw_services")

    # Rename new table to bw_services
    op.rename_table("bw_services_new", "bw_services")

    # bw_services_settings
    op.create_table(
        "bw_services_settings_new",
        sa.Column("service_id", sa.String(256), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("value", sa.TEXT, nullable=False),
        sa.Column("suffix", sa.Integer, nullable=True, default=0),
        sa.Column("method", postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False), nullable=False),
        sa.PrimaryKeyConstraint("service_id", "setting_id", "suffix"),
    )

    op.execute(
        """
        INSERT INTO bw_services_settings_new (service_id, setting_id, value, suffix, method)
        SELECT service_id, setting_id, value, suffix, method FROM bw_services_settings
    """
    )

    op.drop_table("bw_services_settings")
    op.rename_table("bw_services_settings_new", "bw_services_settings")

    # bw_custom_configs
    op.create_table(
        "bw_custom_configs_new",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("service_id", sa.String(256), nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(
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
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("method", postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False), nullable=False),
        sa.UniqueConstraint("service_id", "type", "name"),
    )

    op.execute(
        """
        INSERT INTO bw_custom_configs_new (id, service_id, type, name, data, checksum, method)
        SELECT id, service_id, type, name, data, checksum, method
        FROM bw_custom_configs
    """
    )

    op.drop_table("bw_custom_configs")
    op.rename_table("bw_custom_configs_new", "bw_custom_configs")

    # bw_jobs_cache
    op.create_table(
        "bw_jobs_cache_new",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("job_name", sa.String(128), nullable=False),
        sa.Column("service_id", sa.String(256), nullable=True),
        sa.Column("file_name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=True),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
    )

    op.execute(
        """
        INSERT INTO bw_jobs_cache_new (id, job_name, service_id, file_name, data, last_update, checksum)
        SELECT id, job_name, service_id, file_name, data, last_update, checksum FROM bw_jobs_cache
    """
    )

    op.drop_table("bw_jobs_cache")
    op.rename_table("bw_jobs_cache_new", "bw_jobs_cache")

    # Recreate foreign keys referencing bw_services now that bw_services is updated
    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.create_foreign_key("bw_custom_configs_service_id_fkey", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.create_foreign_key("bw_services_settings_service_id_fkey", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.create_foreign_key("bw_jobs_cache_service_id_fkey", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    # Update bw_instances.status from Enum("loading", "up", "down", name="instance_status_enum") to Enum("loading", "up", "down", "failover", name="instance_status_enum")
    op.execute("ALTER TYPE instance_status_enum ADD VALUE 'failover'")

    # Check if bw_instances.status has instance_type_enum type and replace it with instance_status_enum if needed
    with op.batch_alter_table("bw_instances") as batch_op:
        # Create temporary column with new enum type
        batch_op.add_column(
            sa.Column("status_new", postgresql.ENUM("loading", "up", "down", "failover", name="instance_status_enum", create_type=False), nullable=True)
        )
    # Copy data to new column
    op.execute("UPDATE bw_instances SET status_new = status::text::instance_status_enum")
    # Drop old column
    batch_op.drop_column("status")
    # Rename new column to status
    batch_op.alter_column("status_new", new_column_name="status", nullable=False)

    # Add the new order column to bw_template_settings
    # Step 1: Add column as nullable
    op.add_column("bw_template_settings", sa.Column("order", sa.Integer(), nullable=True))

    # Step 2: Populate default values
    op.execute('UPDATE bw_template_settings SET "order" = 0')

    # Step 3: Alter column to NOT NULL
    op.alter_column("bw_template_settings", "order", nullable=False)

    # Add the new order column to bw_template_custom_configs
    # Step 1: Add column as nullable
    op.add_column("bw_template_custom_configs", sa.Column("order", sa.Integer(), nullable=True))

    # Step 2: Populate default values
    op.execute('UPDATE bw_template_custom_configs SET "order" = 0')

    # Step 3: Alter column to NOT NULL
    op.alter_column("bw_template_custom_configs", "order", nullable=False)

    # First drop Identity properties
    op.execute(
        """
        ALTER TABLE bw_plugin_pages ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_jobs_cache ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_jobs_runs ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_custom_configs ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_cli_commands ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_template_settings ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_template_custom_configs ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_ui_user_recovery_codes ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_ui_user_sessions ALTER COLUMN id DROP IDENTITY IF EXISTS;
        ALTER TABLE bw_ui_user_columns_preferences ALTER COLUMN id DROP IDENTITY IF EXISTS;
    """
    )

    # Create sequences
    op.execute(
        """
        CREATE SEQUENCE IF NOT EXISTS bw_plugin_pages_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_jobs_cache_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_jobs_runs_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_custom_configs_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_cli_commands_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_template_settings_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_template_custom_configs_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_ui_user_recovery_codes_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_ui_user_sessions_id_seq;
        CREATE SEQUENCE IF NOT EXISTS bw_ui_user_columns_preferences_id_seq;
    """
    )

    # Set sequence values
    op.execute(
        """
        SELECT setval('bw_plugin_pages_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_plugin_pages));
        SELECT setval('bw_jobs_cache_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_jobs_cache));
        SELECT setval('bw_jobs_runs_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_jobs_runs));
        SELECT setval('bw_custom_configs_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_custom_configs));
        SELECT setval('bw_cli_commands_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_cli_commands));
        SELECT setval('bw_template_settings_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_template_settings));
        SELECT setval('bw_template_custom_configs_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_template_custom_configs));
        SELECT setval('bw_ui_user_recovery_codes_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_ui_user_recovery_codes));
        SELECT setval('bw_ui_user_sessions_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_ui_user_sessions));
        SELECT setval('bw_ui_user_columns_preferences_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bw_ui_user_columns_preferences));
    """
    )

    # Set column defaults
    op.execute(
        """
        ALTER TABLE bw_plugin_pages ALTER COLUMN id SET DEFAULT nextval('bw_plugin_pages_id_seq');
        ALTER TABLE bw_jobs_cache ALTER COLUMN id SET DEFAULT nextval('bw_jobs_cache_id_seq');
        ALTER TABLE bw_jobs_runs ALTER COLUMN id SET DEFAULT nextval('bw_jobs_runs_id_seq');
        ALTER TABLE bw_custom_configs ALTER COLUMN id SET DEFAULT nextval('bw_custom_configs_id_seq');
        ALTER TABLE bw_cli_commands ALTER COLUMN id SET DEFAULT nextval('bw_cli_commands_id_seq');
        ALTER TABLE bw_template_settings ALTER COLUMN id SET DEFAULT nextval('bw_template_settings_id_seq');
        ALTER TABLE bw_template_custom_configs ALTER COLUMN id SET DEFAULT nextval('bw_template_custom_configs_id_seq');
        ALTER TABLE bw_ui_user_recovery_codes ALTER COLUMN id SET DEFAULT nextval('bw_ui_user_recovery_codes_id_seq');
        ALTER TABLE bw_ui_user_sessions ALTER COLUMN id SET DEFAULT nextval('bw_ui_user_sessions_id_seq');
        ALTER TABLE bw_ui_user_columns_preferences ALTER COLUMN id SET DEFAULT nextval('bw_ui_user_columns_preferences_id_seq');
    """
    )

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc1' WHERE id = 1")


def downgrade() -> None:
    # Drop foreign keys referencing bw_services before reverting changes
    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.drop_constraint("bw_jobs_cache_service_id_fkey", type_="foreignkey")

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.drop_constraint("bw_services_settings_service_id_fkey", type_="foreignkey")

    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.drop_constraint("bw_custom_configs_service_id_fkey", type_="foreignkey")

    # Revert bw_jobs_cache
    op.create_table(
        "bw_jobs_cache_old",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("job_name", sa.String(128), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=True),
        sa.Column("file_name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=True),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
    )

    op.execute(
        """
        INSERT INTO bw_jobs_cache_old (id, job_name, service_id, file_name, data, last_update, checksum)
        SELECT id, job_name, service_id, file_name, data, last_update, checksum FROM bw_jobs_cache
    """
    )

    op.drop_table("bw_jobs_cache")
    op.rename_table("bw_jobs_cache_old", "bw_jobs_cache")

    # Revert bw_custom_configs
    op.create_table(
        "bw_custom_configs_old",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("service_id", sa.String(64), nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(
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
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column(
            "method",
            postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False),
            nullable=False,
        ),
        sa.UniqueConstraint("service_id", "type", "name"),
    )

    op.execute(
        """
        INSERT INTO bw_custom_configs_old (id, service_id, type, name, data, checksum, method)
        SELECT id, service_id, type, name, data, checksum, method FROM bw_custom_configs
    """
    )

    op.drop_table("bw_custom_configs")
    op.rename_table("bw_custom_configs_old", "bw_custom_configs")

    # Revert bw_services_settings
    op.create_table(
        "bw_services_settings_old",
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("value", sa.TEXT, nullable=False),
        sa.Column("suffix", sa.Integer, nullable=True, default=0),
        sa.Column(
            "method",
            postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("service_id", "setting_id", "suffix"),
    )

    op.execute(
        """
        INSERT INTO bw_services_settings_old (service_id, setting_id, value, suffix, method)
        SELECT service_id, setting_id, value, suffix, method FROM bw_services_settings
    """
    )

    op.drop_table("bw_services_settings")
    op.rename_table("bw_services_settings_old", "bw_services_settings")

    # Revert bw_services
    op.create_table(
        "bw_services_old",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("method", postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False), nullable=False),
        sa.Column("is_draft", sa.Boolean, default=False, nullable=False),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=False),
    )

    op.execute(
        """
        INSERT INTO bw_services_old (id, method, is_draft, creation_date, last_update)
        SELECT id, method, is_draft, creation_date, last_update FROM bw_services
    """
    )

    op.drop_table("bw_services")
    op.rename_table("bw_services_old", "bw_services")

    # Recreate foreign keys referencing bw_services
    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.create_foreign_key("bw_custom_configs_service_id_fkey", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.create_foreign_key("bw_services_settings_service_id_fkey", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.create_foreign_key("bw_jobs_cache_service_id_fkey", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    # Update bw_instances.status from Enum("loading", "up", "down", "failover", name="instance_status_enum") to Enum("loading", "up", "down", name="instance_status_enum")
    op.execute("ALTER TYPE instance_status_enum DROP VALUE 'failover'")

    # Drop 'order' column from 'bw_template_settings'
    with op.batch_alter_table("bw_template_settings") as batch_op:
        batch_op.drop_column("order")

    # Drop 'order' column from 'bw_template_custom_configs'
    with op.batch_alter_table("bw_template_custom_configs") as batch_op:
        batch_op.drop_column("order")

    # Revert version
    op.execute("UPDATE bw_metadata SET version = '1.6.0-beta' WHERE id = 1")
