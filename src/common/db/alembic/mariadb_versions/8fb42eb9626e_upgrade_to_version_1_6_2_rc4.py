"""Upgrade to version 1.6.2-rc4

Revision ID: 8fb42eb9626e
Revises: 5db76033c2ab
Create Date: 2025-06-10 15:48:11.866859

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "8fb42eb9626e"
down_revision: Union[str, None] = "5db76033c2ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bw_multiselects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setting_id", sa.String(length=256), nullable=False),
        sa.Column("option_id", sa.String(length=256), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="cascade", ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setting_id", "option_id"),
        sa.UniqueConstraint("setting_id", "order"),
    )

    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=mysql.ENUM("password", "text", "check", "select"),
            type_=mysql.ENUM("password", "text", "check", "select", "multiselect"),
            existing_nullable=False,
        )

    with op.batch_alter_table("bw_ui_user_sessions") as batch_op:
        batch_op.alter_column("id", existing_type=mysql.VARCHAR(length=256), type_=sa.Integer(), existing_nullable=False, autoincrement=True)

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc4' WHERE id = 1")


def downgrade() -> None:
    with op.batch_alter_table("bw_ui_user_sessions") as batch_op:
        batch_op.alter_column("id", existing_type=sa.Integer(), type_=mysql.VARCHAR(length=256), existing_nullable=False, autoincrement=True)

    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=mysql.ENUM("password", "text", "check", "select", "multiselect"),
            type_=mysql.ENUM("password", "text", "check", "select"),
            existing_nullable=False,
        )

    op.drop_table("bw_multiselects")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc3' WHERE id = 1")
