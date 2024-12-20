"""Upgrade to version 1.6.0-rc1

Revision ID: 6307fa627563
Revises: 839424d81cf7
Create Date: 2024-12-20 10:41:52.149076

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "6307fa627563"
down_revision: Union[str, None] = "839424d81cf7"
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

    # Update bw_settings.default from String(4096) to TEXT
    op.alter_column("bw_settings", "default", existing_type=mysql.VARCHAR(length=4096), type_=sa.TEXT(), existing_nullable=True)

    # Drop bw_ui_users.id column
    op.drop_column("bw_ui_users", "id")

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

    op.alter_column("bw_settings", "default", existing_type=sa.TEXT(), type_=mysql.VARCHAR(length=4096), existing_nullable=True)

    # Re-add bw_ui_users.id and index on username
    op.add_column("bw_ui_users", sa.Column("id", sa.Integer(), autoincrement=True, nullable=False))

    # Revert version
    op.execute("UPDATE bw_metadata SET version = '1.6.0-beta' WHERE id = 1")
