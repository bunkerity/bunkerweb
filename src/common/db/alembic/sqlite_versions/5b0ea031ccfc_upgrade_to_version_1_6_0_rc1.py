"""Upgrade to version 1.6.0-rc1

Revision ID: 5b0ea031ccfc
Revises: 1e1fc017a424
Create Date: 2024-12-20 08:36:31.739835

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b0ea031ccfc"
down_revision: Union[str, None] = "1e1fc017a424"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable foreign key checks (SQLite specific)
    op.execute("PRAGMA foreign_keys=OFF;")

    # --- bw_services ---
    # Old schema (1.6.0-beta):
    # id: String(64), method: METHODS_ENUM, is_draft: Boolean, creation_date: DateTime, last_update: DateTime
    # New schema (1.6.0-rc1):
    # id: String(256), (other columns unchanged)
    op.create_table(
        "bw_services_new",
        sa.Column("id", sa.String(256), primary_key=True),
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False),
        sa.Column("is_draft", sa.Boolean, default=False, nullable=False),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=False),
    )

    # Copy data from old bw_services to bw_services_new
    op.execute(
        """
        INSERT INTO bw_services_new (id, method, is_draft, creation_date, last_update)
        SELECT id, method, is_draft, creation_date, last_update FROM bw_services
    """
    )

    op.drop_table("bw_services")
    op.rename_table("bw_services_new", "bw_services")

    # --- bw_services_settings ---
    # Old schema:
    # service_id: String(64) FK -> bw_services.id
    # New schema:
    # service_id: String(256) FK -> bw_services.id
    op.create_table(
        "bw_services_settings_new",
        sa.Column("service_id", sa.String(256), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("value", sa.TEXT, nullable=False),
        sa.Column("suffix", sa.Integer, nullable=True, default=0),
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False),
        sa.PrimaryKeyConstraint("service_id", "setting_id", "suffix"),
        sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_services_settings_new (service_id, setting_id, value, suffix, method)
        SELECT service_id, setting_id, value, suffix, method
        FROM bw_services_settings
    """
    )

    op.drop_table("bw_services_settings")
    op.rename_table("bw_services_settings_new", "bw_services_settings")

    # --- bw_custom_configs ---
    # Old schema:
    # service_id: String(64)
    # New schema:
    # service_id: String(256)
    op.create_table(
        "bw_custom_configs_new",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("service_id", sa.String(256), nullable=True),
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
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False),
        sa.UniqueConstraint("service_id", "type", "name"),
        sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_custom_configs_new (id, service_id, type, name, data, checksum, method)
        SELECT id, service_id, type, name, data, checksum, method FROM bw_custom_configs
    """
    )

    op.drop_table("bw_custom_configs")
    op.rename_table("bw_custom_configs_new", "bw_custom_configs")

    # --- bw_jobs_cache ---
    # Old schema:
    # service_id: String(64)
    # New schema:
    # service_id: String(256)
    op.create_table(
        "bw_jobs_cache_new",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("job_name", sa.String(128), nullable=False),
        sa.Column("service_id", sa.String(256), nullable=True),
        sa.Column("file_name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=True),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.ForeignKeyConstraint(["job_name"], ["bw_jobs.name"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_jobs_cache_new (id, job_name, service_id, file_name, data, last_update, checksum)
        SELECT id, job_name, service_id, file_name, data, last_update, checksum FROM bw_jobs_cache
    """
    )

    op.drop_table("bw_jobs_cache")
    op.rename_table("bw_jobs_cache_new", "bw_jobs_cache")

    # --- bw_instances ---
    # Old schema:
    # status: sa.Enum("loading", "up", "down", name="instance_status_enum")
    # New schema:
    # status: Enum("loading", "up", "down", "failover", name="instance_status_enum")
    op.create_table(
        "bw_instances_new",
        sa.Column("hostname", sa.String(256), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False, default="manual instance"),
        sa.Column("port", sa.Integer, nullable=False),
        sa.Column("server_name", sa.String(256), nullable=False),
        sa.Column("type", sa.Enum("static", "container", "pod", name="instance_type_enum"), nullable=False, default="static"),
        sa.Column("status", sa.Enum("loading", "up", "down", "failover", name="instance_status_enum"), nullable=False, default="loading"),
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False, default="manual"),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )

    op.execute(
        """
        INSERT INTO bw_instances_new (hostname, name, port, server_name, type, status, method, creation_date, last_seen)
        SELECT hostname, name, port, server_name, type, status, method, creation_date, last_seen FROM bw_instances
    """
    )

    op.drop_table("bw_instances")
    op.rename_table("bw_instances_new", "bw_instances")

    # Re-enable foreign keys
    op.execute("PRAGMA foreign_keys=ON;")

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc1' WHERE id = 1")


def downgrade() -> None:
    # Disable foreign keys to allow dropping and recreating tables
    op.execute("PRAGMA foreign_keys=OFF;")

    # --- bw_services ---
    # Downgrade: revert id from VARCHAR(256) back to VARCHAR(64)
    op.create_table(
        "bw_services_old",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False),
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

    # --- bw_services_settings ---
    # Downgrade: revert service_id from VARCHAR(256) back to VARCHAR(64)
    op.create_table(
        "bw_services_settings_old",
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("value", sa.TEXT, nullable=False),
        sa.Column("suffix", sa.Integer, nullable=True, default=0),
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False),
        sa.PrimaryKeyConstraint("service_id", "setting_id", "suffix"),
        sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_services_settings_old (service_id, setting_id, value, suffix, method)
        SELECT service_id, setting_id, value, suffix, method FROM bw_services_settings
    """
    )

    op.drop_table("bw_services_settings")
    op.rename_table("bw_services_settings_old", "bw_services_settings")

    # --- bw_custom_configs ---
    # Downgrade: revert service_id from VARCHAR(256) back to VARCHAR(64)
    op.create_table(
        "bw_custom_configs_old",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("service_id", sa.String(64), nullable=True),
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
        sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum"), nullable=False),
        sa.UniqueConstraint("service_id", "type", "name"),
        sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_custom_configs_old (id, service_id, type, name, data, checksum, method)
        SELECT id, service_id, type, name, data, checksum, method FROM bw_custom_configs
    """
    )

    op.drop_table("bw_custom_configs")
    op.rename_table("bw_custom_configs_old", "bw_custom_configs")

    # --- bw_jobs_cache ---
    # Downgrade: revert service_id from VARCHAR(256) back to VARCHAR(64)
    op.create_table(
        "bw_jobs_cache_old",
        sa.Column("id", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("job_name", sa.String(128), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=True),
        sa.Column("file_name", sa.String(256), nullable=False),
        sa.Column("data", sa.LargeBinary(length=(2**32) - 1), nullable=True),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.ForeignKeyConstraint(["job_name"], ["bw_jobs.name"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="CASCADE", ondelete="CASCADE"),
    )

    op.execute(
        """
        INSERT INTO bw_jobs_cache_old (id, job_name, service_id, file_name, data, last_update, checksum)
        SELECT id, job_name, service_id, file_name, data, last_update, checksum FROM bw_jobs_cache
    """
    )

    op.drop_table("bw_jobs_cache")
    op.rename_table("bw_jobs_cache_old", "bw_jobs_cache")

    # Re-enable foreign keys
    op.execute("PRAGMA foreign_keys=ON;")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-beta' WHERE id = 1")
