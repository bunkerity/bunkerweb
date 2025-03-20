"""Upgrade to version 1.6.2-rc1

Revision ID: f29b02a768e8
Revises: c4b4f7aeaa18
Create Date: 2025-03-20 13:34:43.072624

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import MetaData, Table

# revision identifiers, used by Alembic.
revision: str = "f29b02a768e8"
down_revision: Union[str, None] = "c4b4f7aeaa18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    metadata = MetaData()

    # Handle bw_global_values table
    # Create temp table
    op.create_table(
        "bw_global_values_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("suffix", sa.Integer(), nullable=True),
        sa.Column("method", postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="cascade", ondelete="cascade"),
        sa.UniqueConstraint("setting_id", "suffix"),
    )

    # Copy data
    bw_global_values = Table("bw_global_values", metadata, autoload_with=conn)
    bw_global_values_new = Table("bw_global_values_new", metadata, autoload_with=conn)

    data = conn.execute(
        sa.select(
            bw_global_values.c.setting_id,
            bw_global_values.c.value,
            bw_global_values.c.suffix,
            bw_global_values.c.method,
        )
    ).fetchall()
    if data:
        conn.execute(bw_global_values_new.insert().values([{"setting_id": r[0], "value": r[1], "suffix": r[2], "method": r[3]} for r in data]))

    # Drop old table and rename new one
    op.drop_table("bw_global_values")
    op.rename_table("bw_global_values_new", "bw_global_values")

    # Handle bw_selects table
    # Create temp table
    op.create_table(
        "bw_selects_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("value", sa.String(256), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="cascade", ondelete="cascade"),
        sa.UniqueConstraint("setting_id", "value"),
        sa.UniqueConstraint("setting_id", "order"),
    )

    # Copy data
    bw_selects = Table("bw_selects", metadata, autoload_with=conn)
    bw_selects_new = Table("bw_selects_new", metadata, autoload_with=conn)

    data = conn.execute(sa.select(bw_selects.c.setting_id, bw_selects.c.value, bw_selects.c.order)).fetchall()
    if data:
        conn.execute(bw_selects_new.insert().values([{"setting_id": r[0], "value": r[1], "order": r[2]} for r in data]))

    # Drop old table and rename new one
    op.drop_table("bw_selects")
    op.rename_table("bw_selects_new", "bw_selects")

    # Handle bw_services_settings table
    # Create temp table
    op.create_table(
        "bw_services_settings_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_id", sa.String(256), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("suffix", sa.Integer(), nullable=True),
        sa.Column("method", postgresql.ENUM("ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="cascade", ondelete="cascade"),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="cascade", ondelete="cascade"),
        sa.UniqueConstraint("service_id", "setting_id", "suffix"),
    )

    # Copy data
    bw_services_settings = Table("bw_services_settings", metadata, autoload_with=conn)
    bw_services_settings_new = Table("bw_services_settings_new", metadata, autoload_with=conn)

    data = conn.execute(
        sa.select(
            bw_services_settings.c.service_id,
            bw_services_settings.c.setting_id,
            bw_services_settings.c.value,
            bw_services_settings.c.suffix,
            bw_services_settings.c.method,
        )
    ).fetchall()
    if data:
        conn.execute(
            bw_services_settings_new.insert().values([{"service_id": r[0], "setting_id": r[1], "value": r[2], "suffix": r[3], "method": r[4]} for r in data])
        )

    # Drop old table and rename new one
    op.drop_table("bw_services_settings")
    op.rename_table("bw_services_settings_new", "bw_services_settings")

    # Handle bw_template_settings table
    # Create temp table with the desired structure
    op.create_table(
        "bw_template_settings_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.String(256), nullable=False),
        sa.Column("setting_id", sa.String(256), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=False),
        sa.Column("default", sa.Text(), nullable=True),
        sa.Column("suffix", sa.Integer(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["template_id"], ["bw_templates.id"], onupdate="cascade", ondelete="cascade"),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="cascade", ondelete="cascade"),
        sa.UniqueConstraint("template_id", "setting_id", "step_id", "suffix"),
        sa.UniqueConstraint("template_id", "setting_id", "order"),
    )

    # Copy data
    bw_template_settings = Table("bw_template_settings", metadata, autoload_with=conn)
    bw_template_settings_new = Table("bw_template_settings_new", metadata, autoload_with=conn)

    data = conn.execute(
        sa.select(
            bw_template_settings.c.template_id,
            bw_template_settings.c.setting_id,
            bw_template_settings.c.step_id,
            bw_template_settings.c.default,
            bw_template_settings.c.suffix,
            bw_template_settings.c.order,
        )
    ).fetchall()
    if data:
        conn.execute(
            bw_template_settings_new.insert().values(
                [{"template_id": r[0], "setting_id": r[1], "step_id": r[2], "default": r[3], "suffix": r[4], "order": r[5]} for r in data]
            )
        )

    # Drop old table and rename new one
    op.drop_table("bw_template_settings")
    op.rename_table("bw_template_settings_new", "bw_template_settings")

    # Handle bw_ui_user_sessions table
    # Create temp table with the desired structure
    op.create_table(
        "bw_ui_user_sessions_new",
        sa.Column("id", sa.String(256), nullable=False),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("ip", sa.String(39), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_name"], ["bw_ui_users.username"], onupdate="cascade", ondelete="cascade"),
    )

    # Copy data
    bw_ui_user_sessions = Table("bw_ui_user_sessions", metadata, autoload_with=conn)
    bw_ui_user_sessions_new = Table("bw_ui_user_sessions_new", metadata, autoload_with=conn)

    data = conn.execute(
        sa.select(
            bw_ui_user_sessions.c.id,
            bw_ui_user_sessions.c.user_name,
            bw_ui_user_sessions.c.ip,
            bw_ui_user_sessions.c.user_agent,
            bw_ui_user_sessions.c.creation_date,
            bw_ui_user_sessions.c.last_activity,
        )
    ).fetchall()
    if data:
        conn.execute(
            bw_ui_user_sessions_new.insert().values(
                [
                    {
                        "id": r[0],
                        "user_name": r[1],
                        "ip": r[2],
                        "user_agent": r[3],
                        "creation_date": r[4],
                        "last_activity": r[5],
                    }
                    for r in data
                ]
            )
        )

    # Drop old table and rename new one
    op.drop_table("bw_ui_user_sessions")
    op.rename_table("bw_ui_user_sessions_new", "bw_ui_user_sessions")

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc1' WHERE id = 1")


def downgrade() -> None:
    pass
