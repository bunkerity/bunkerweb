"""Upgrade to version 1.6.5-rc4

Revision ID: 8aa2b3429298
Revises: 0fd76e951eac
Create Date: 2025-09-19 14:00:36.658418

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8aa2b3429298"
down_revision: Union[str, None] = "0fd76e951eac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE methods_enum ADD VALUE 'api'")

    op.create_table(
        "bw_api_users",
        sa.Column("username", sa.String(length=256), nullable=False),
        sa.Column("password", sa.String(length=60), nullable=False),
        sa.Column("method", postgresql.ENUM("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False), nullable=False),
        sa.Column("admin", sa.Boolean(), nullable=False),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_date", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("username"),
    )
    op.create_table(
        "bw_api_user_permissions",
        sa.Column("id", sa.Integer(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.Column("api_user", sa.String(length=256), nullable=False),
        sa.Column(
            "resource_type",
            postgresql.ENUM("instances", "global_config", "services", "configs", "plugins", "cache", "bans", "jobs", name="api_resource_enum"),
            nullable=False,
        ),
        sa.Column("resource_id", sa.String(length=256), nullable=True),
        sa.Column("permission", sa.String(length=512), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_user"], ["bw_api_users.username"], onupdate="cascade", ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("bw_instances", sa.Column("listen_https", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("bw_instances", sa.Column("https_port", sa.Integer(), nullable=False, server_default=sa.text("6000")))
    op.alter_column("bw_metadata", "pro_expire", existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), existing_nullable=True)
    op.alter_column("bw_metadata", "last_pro_check", existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), existing_nullable=True)
    op.alter_column("bw_metadata", "last_custom_configs_change", existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), existing_nullable=True)
    op.alter_column(
        "bw_metadata", "last_external_plugins_change", existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), existing_nullable=True
    )
    op.alter_column("bw_metadata", "last_pro_plugins_change", existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), existing_nullable=True)
    op.alter_column("bw_metadata", "last_instances_change", existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), existing_nullable=True)
    op.alter_column("bw_plugins", "last_config_change", existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), existing_nullable=True)
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc4' WHERE id = 1")


def downgrade() -> None:
    op.create_unique_constraint(op.f("bw_ui_users_username_key"), "bw_ui_users", ["username"], postgresql_nulls_not_distinct=False)
    op.alter_column("bw_plugins", "last_config_change", existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=True)
    op.alter_column("bw_metadata", "last_instances_change", existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=True)
    op.alter_column("bw_metadata", "last_pro_plugins_change", existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=True)
    op.alter_column(
        "bw_metadata", "last_external_plugins_change", existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=True
    )
    op.alter_column("bw_metadata", "last_custom_configs_change", existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=True)
    op.alter_column("bw_metadata", "last_pro_check", existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=True)
    op.alter_column("bw_metadata", "pro_expire", existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=True)
    op.drop_column("bw_instances", "https_port")
    op.drop_column("bw_instances", "listen_https")
    op.drop_table("bw_api_user_permissions")
    op.drop_table("bw_api_users")
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc3' WHERE id = 1")
