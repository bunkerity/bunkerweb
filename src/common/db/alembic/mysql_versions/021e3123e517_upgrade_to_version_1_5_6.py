"""Upgrade to version 1.5.6

Revision ID: 021e3123e517
Revises: 0903238e095e
Create Date: 2024-12-19 13:23:02.905461

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "021e3123e517"
down_revision: Union[str, None] = "0903238e095e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Drop the foreign key constraint with the correct name
    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.drop_constraint("bw_jobs_cache_ibfk_1", type_="foreignkey")  # Replace with actual name
        batch_op.drop_index("job_name")
        batch_op.create_foreign_key("fk_bw_jobs_cache_job_name", "bw_jobs", ["job_name"], ["name"])

    # Other migration operations
    op.add_column("bw_metadata", sa.Column("is_pro", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("bw_metadata", sa.Column("pro_expire", sa.DateTime(), nullable=True))
    op.add_column(
        "bw_metadata",
        sa.Column("pro_status", sa.Enum("active", "invalid", "expired", "suspended", name="pro_status_enum"), nullable=False, server_default="invalid"),
    )
    op.add_column("bw_metadata", sa.Column("pro_services", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bw_metadata", sa.Column("pro_overlapped", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("bw_metadata", sa.Column("last_pro_check", sa.DateTime(), nullable=True))
    op.add_column("bw_metadata", sa.Column("pro_plugins_changed", sa.Boolean(), nullable=True))

    op.add_column("bw_services", sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("bw_plugins", sa.Column("type", sa.Enum("core", "external", "pro", name="plugin_types_enum"), nullable=False, server_default="core"))
    op.alter_column(
        "bw_plugins", "stream", existing_type=mysql.VARCHAR(length=16), type_=sa.Enum("no", "yes", "partial", name="stream_types_enum"), existing_nullable=False
    )

    # Migrate data: Set 'type' to 'external' where 'external' was true
    op.execute(
        """
        UPDATE bw_plugins
        SET type = 'external'
        WHERE external = true
    """
    )

    op.drop_column("bw_plugins", "external")

    op.alter_column("bw_global_values", "value", existing_type=mysql.VARCHAR(length=8192), type_=sa.TEXT(), existing_nullable=False)
    op.alter_column("bw_services_settings", "value", existing_type=mysql.VARCHAR(length=8192), type_=sa.TEXT(), existing_nullable=False)

    op.drop_index("name", table_name="bw_jobs")
    op.drop_index("name", table_name="bw_settings")

    # Update all new columns and version in a single statement
    op.execute(
        """
        UPDATE bw_metadata
        SET is_pro = false,
            pro_status = 'invalid',
            pro_services = 0,
            pro_overlapped = false,
            pro_plugins_changed = false,
            version = '1.5.6'
        WHERE id = 1
    """
    )


def downgrade():
    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.drop_constraint("fk_bw_jobs_cache_job_name", type_="foreignkey")
        batch_op.create_index("job_name", ["job_name", "service_id", "file_name"], unique=True)
        batch_op.create_foreign_key("bw_jobs_cache_ibfk_1", "bw_jobs", ["job_name"], ["name"])  # Replace with actual name

    op.create_index("name", "bw_jobs", ["name", "plugin_id"], unique=True)
    op.create_index("name", "bw_settings", ["name"], unique=True)

    op.alter_column("bw_global_values", "value", existing_type=sa.TEXT(), type_=mysql.VARCHAR(length=8192), existing_nullable=False)
    op.alter_column("bw_services_settings", "value", existing_type=sa.TEXT(), type_=mysql.VARCHAR(length=8192), existing_nullable=False)

    op.add_column("bw_plugins", sa.Column("external", mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))

    # Migrate data: Set 'external' to true where 'type' was 'external'
    op.execute(
        """
        UPDATE bw_plugins
        SET external = true
        WHERE type = 'external'
    """
    )

    op.drop_column("bw_plugins", "type")
    op.alter_column(
        "bw_plugins", "stream", existing_type=sa.Enum("no", "yes", "partial", name="stream_types_enum"), type_=mysql.VARCHAR(length=16), existing_nullable=False
    )

    op.drop_column("bw_services", "is_draft")

    op.drop_column("bw_metadata", "pro_plugins_changed")
    op.drop_column("bw_metadata", "last_pro_check")
    op.drop_column("bw_metadata", "pro_overlapped")
    op.drop_column("bw_metadata", "pro_services")
    op.drop_column("bw_metadata", "pro_status")
    op.drop_column("bw_metadata", "pro_expire")
    op.drop_column("bw_metadata", "is_pro")

    op.execute("UPDATE bw_metadata SET version = '1.5.5' WHERE id = 1")
