"""Upgrade to version 1.6.0-rc1

Revision ID: 8a37fed772e9
Revises: bfa7869e34c3
Create Date: 2024-12-20 10:19:30.469285

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "8a37fed772e9"
down_revision: Union[str, None] = "bfa7869e34c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop foreign keys referencing service_id columns before altering them
    # Replace these FK names with the actual names in your schema
    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.drop_constraint("bw_custom_configs_ibfk_1", type_="foreignkey")
    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.drop_constraint("bw_jobs_cache_ibfk_2", type_="foreignkey")
    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.drop_constraint("bw_services_settings_ibfk_1", type_="foreignkey")

    # Alter columns now that foreign keys are dropped
    op.alter_column("bw_custom_configs", "service_id", existing_type=mysql.VARCHAR(length=64), type_=sa.String(length=256), existing_nullable=True)

    op.alter_column("bw_jobs_cache", "service_id", existing_type=mysql.VARCHAR(length=64), type_=sa.String(length=256), existing_nullable=True)

    op.alter_column("bw_services", "id", existing_type=mysql.VARCHAR(length=64), type_=sa.String(length=256), existing_nullable=False)

    op.alter_column("bw_services_settings", "service_id", existing_type=mysql.VARCHAR(length=64), type_=sa.String(length=256), existing_nullable=False)

    # After altering, recreate the foreign keys with updated references
    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.create_foreign_key("bw_custom_configs_ibfk_1", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.create_foreign_key("bw_jobs_cache_ibfk_2", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.create_foreign_key("bw_services_settings_ibfk_1", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    # Update bw_instances.status from Enum("loading", "up", "down", name="instance_status_enum") to Enum("loading", "up", "down", "failover", name="instance_status_enum")
    op.alter_column(
        "bw_instances",
        "status",
        existing_type=mysql.ENUM("loading", "up", "down", name="instance_status_enum"),
        type_=mysql.ENUM("loading", "up", "down", "failover", name="instance_status_enum"),
        existing_nullable=False,
    )

    # Drop bw_ui_users.id column if it exists
    with op.batch_alter_table("bw_ui_users") as batch_op:
        if "id" in [c["name"] for c in batch_op.impl.dialect.get_columns(op.get_bind(), "bw_ui_users")]:
            batch_op.drop_column("id")

    # Add the new order column to bw_template_settings
    op.add_column("bw_template_settings", sa.Column("order", sa.Integer(), nullable=False))

    # Add the new order column to bw_template_custom_configs
    op.add_column("bw_template_custom_configs", sa.Column("order", sa.Integer(), nullable=False))

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc1' WHERE id = 1")


def downgrade() -> None:
    # Reverse the changes:
    # 1. Drop foreign keys
    # 2. Revert column types
    # 3. Recreate foreign keys
    # 4. Revert version
    # 5. Re-add bw_ui_users.id column

    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.drop_constraint("bw_custom_configs_ibfk_1", type_="foreignkey")
    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.drop_constraint("bw_jobs_cache_ibfk_1", type_="foreignkey")
    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.drop_constraint("bw_services_settings_ibfk_1", type_="foreignkey")

    op.alter_column("bw_services_settings", "service_id", existing_type=sa.String(length=256), type_=mysql.VARCHAR(length=64), existing_nullable=False)

    op.alter_column("bw_services", "id", existing_type=sa.String(length=256), type_=mysql.VARCHAR(length=64), existing_nullable=False)

    op.alter_column("bw_jobs_cache", "service_id", existing_type=sa.String(length=256), type_=mysql.VARCHAR(length=64), existing_nullable=True)

    op.alter_column("bw_custom_configs", "service_id", existing_type=sa.String(length=256), type_=mysql.VARCHAR(length=64), existing_nullable=True)

    # Recreate foreign keys with old definitions
    with op.batch_alter_table("bw_custom_configs") as batch_op:
        batch_op.create_foreign_key("bw_custom_configs_ibfk_1", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.create_foreign_key("bw_jobs_cache_ibfk_1", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.create_foreign_key("bw_services_settings_ibfk_1", "bw_services", ["service_id"], ["id"], onupdate="CASCADE", ondelete="CASCADE")

    op.alter_column(
        "bw_instances",
        "status",
        existing_type=mysql.ENUM("loading", "up", "down", "failover", name="instance_status_enum"),
        type_=mysql.ENUM("loading", "up", "down", name="instance_status_enum"),
        existing_nullable=False,
    )

    # Drop the order column from bw_template_settings
    op.drop_column("bw_template_settings", "order")

    # Drop the order column from bw_template_custom_configs
    op.drop_column("bw_template_custom_configs", "order")

    # Revert version
    op.execute("UPDATE bw_metadata SET version = '1.6.0-beta' WHERE id = 1")
