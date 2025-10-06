"""Upgrade to version 1.6.5

Revision ID: a06ce1d36991
Revises: fd214d08928f
Create Date: 2025-09-26 13:13:46.312029

"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a06ce1d36991"
down_revision: Union[str, None] = "fd214d08928f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    current_timestamp = datetime.now(timezone.utc)
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Only create bw_api_users if it doesn't exist
    if "bw_api_users" not in inspector.get_table_names():
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

    # Only create bw_api_user_permissions if it doesn't exist
    if "bw_api_user_permissions" not in inspector.get_table_names():
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

    # Check if columns exist before adding them - use batch_alter_table for SQLite
    columns = [col["name"] for col in inspector.get_columns("bw_instances")]
    with op.batch_alter_table("bw_instances") as batch_op:
        if "listen_https" not in columns:
            batch_op.add_column(sa.Column("listen_https", sa.Boolean(), nullable=True))
        if "https_port" not in columns:
            batch_op.add_column(sa.Column("https_port", sa.Integer(), nullable=True))

    template_columns = [col["name"] for col in inspector.get_columns("bw_templates")]
    with op.batch_alter_table("bw_templates") as batch_op:
        if "method" not in template_columns:
            batch_op.add_column(sa.Column("method", sa.Enum("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"), nullable=True))
        if "creation_date" not in template_columns:
            batch_op.add_column(sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True))
        if "last_update" not in template_columns:
            batch_op.add_column(sa.Column("last_update", sa.DateTime(timezone=True), nullable=True))
        # Alter plugin_id to be nullable
        batch_op.alter_column(
            "plugin_id",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            nullable=True,
        )

    # Update with defaults after adding columns
    bind.execute(
        sa.text("UPDATE bw_instances SET listen_https = :listen_https WHERE listen_https IS NULL"),
        {"listen_https": False},
    )
    bind.execute(
        sa.text("UPDATE bw_instances SET https_port = :https_port WHERE https_port IS NULL"),
        {"https_port": 5443},
    )
    bind.execute(
        sa.text("UPDATE bw_templates SET method = :method WHERE method IS NULL"),
        {"method": "manual"},
    )
    bind.execute(
        sa.text("UPDATE bw_templates SET creation_date = :ts WHERE creation_date IS NULL"),
        {"ts": current_timestamp},
    )
    bind.execute(
        sa.text("UPDATE bw_templates SET last_update = :ts WHERE last_update IS NULL"),
        {"ts": current_timestamp},
    )

    # Make columns NOT NULL after setting defaults
    with op.batch_alter_table("bw_instances") as batch_op:
        if "listen_https" in columns or "listen_https" not in [col["name"] for col in inspector.get_columns("bw_instances")]:
            batch_op.alter_column("listen_https", existing_type=sa.Boolean(), nullable=False)
        if "https_port" in columns or "https_port" not in [col["name"] for col in inspector.get_columns("bw_instances")]:
            batch_op.alter_column("https_port", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("bw_templates") as batch_op:
        if "method" in template_columns or "method" not in [col["name"] for col in inspector.get_columns("bw_templates")]:
            batch_op.alter_column(
                "method",
                existing_type=sa.Enum("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum"),
                nullable=False,
            )
        if "creation_date" in template_columns or "creation_date" not in [col["name"] for col in inspector.get_columns("bw_templates")]:
            batch_op.alter_column("creation_date", existing_type=sa.DateTime(timezone=True), nullable=False)
        if "last_update" in template_columns or "last_update" not in [col["name"] for col in inspector.get_columns("bw_templates")]:
            batch_op.alter_column("last_update", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.execute("UPDATE bw_metadata SET version = '1.6.5' WHERE id = 1")


def downgrade() -> None:
    with op.batch_alter_table("bw_templates") as batch_op:
        batch_op.alter_column(
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
