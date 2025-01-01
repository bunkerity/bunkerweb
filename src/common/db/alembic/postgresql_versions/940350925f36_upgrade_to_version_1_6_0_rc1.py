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
    op.alter_column(
        "bw_instances",
        "status",
        existing_type=postgresql.ENUM("loading", "up", "down", name="instance_status_enum", create_type=False),
        type_=postgresql.ENUM("loading", "up", "down", "failover", name="instance_status_enum", create_type=False),
        existing_nullable=False,
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
    op.alter_column(
        "bw_instances",
        "status",
        existing_type=postgresql.ENUM("loading", "up", "down", "failover", name="instance_status_enum", create_type=False),
        type_=postgresql.ENUM("loading", "up", "down", name="instance_status_enum", create_type=False),
        existing_nullable=False,
    )

    # Revert version
    op.execute("UPDATE bw_metadata SET version = '1.6.0-beta' WHERE id = 1")
