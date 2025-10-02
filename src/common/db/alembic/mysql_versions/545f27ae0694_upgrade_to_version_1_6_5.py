"""Upgrade to version 1.6.5

Revision ID: 545f27ae0694
Revises: 2c8a1caf53fa
Create Date: 2025-09-26 13:25:23.705710

"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "545f27ae0694"
down_revision: Union[str, None] = "2c8a1caf53fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    current_timestamp = datetime.now(timezone.utc)
    bind = op.get_bind()
    op.create_table(
        "bw_api_users",
        sa.Column("username", sa.String(length=256), nullable=False),
        sa.Column("password", sa.String(length=60), nullable=False),
        sa.Column("method", sa.Enum("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=False),
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
            sa.Enum("instances", "global_config", "services", "configs", "plugins", "cache", "bans", "jobs", name="api_resource_enum"),
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
    op.add_column(
        "bw_instances",
        sa.Column("listen_https", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "bw_instances",
        sa.Column("https_port", sa.Integer(), nullable=False, server_default=sa.text("5443")),
    )
    op.add_column(
        "bw_templates",
        sa.Column(
            "method",
            sa.Enum("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
    )
    op.add_column(
        "bw_templates",
        sa.Column(
            "creation_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "bw_templates",
        sa.Column(
            "last_update",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    bind.execute(
        sa.text("UPDATE bw_instances SET listen_https = :listen_https, https_port = :https_port"),
        {"listen_https": False, "https_port": 5443},
    )
    bind.execute(
        sa.text("UPDATE bw_templates SET method = :method, creation_date = :ts, last_update = :ts"),
        {"method": "manual", "ts": current_timestamp},
    )
    op.alter_column(
        "bw_templates",
        "plugin_id",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        nullable=True,
    )
    op.execute("UPDATE bw_metadata SET version = '1.6.5' WHERE id = 1")


def downgrade() -> None:
    op.alter_column(
        "bw_templates",
        "plugin_id",
        existing_type=sa.String(length=64),
        existing_nullable=True,
        nullable=False,
    )
    op.drop_column("bw_templates", "last_update")
    op.drop_column("bw_templates", "creation_date")
    op.drop_column("bw_templates", "method")
    op.drop_column("bw_instances", "https_port")
    op.drop_column("bw_instances", "listen_https")
    op.drop_table("bw_api_user_permissions")
    op.drop_table("bw_api_users")
    op.execute("UPDATE bw_metadata SET version = '1.6.5-rc3' WHERE id = 1")
