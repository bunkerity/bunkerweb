"""Upgrade to version 1.5.5

Revision ID: d4d8df48d14d
Revises: 1cc06aa8335c
Create Date: 2024-12-17 10:19:52.815063

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "d4d8df48d14d"
down_revision: Union[str, None] = "1cc06aa8335c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add new columns to bw_ui_users
    op.add_column("bw_ui_users", sa.Column("is_two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("bw_ui_users", sa.Column("secret_token", sa.String(length=32), nullable=True))
    op.add_column(
        "bw_ui_users", sa.Column("method", sa.Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum"), nullable=False, server_default="manual")
    )
    op.create_unique_constraint("uq_bw_ui_users_secret_token", "bw_ui_users", ["secret_token"])

    # Increase column sizes
    op.alter_column("bw_global_values", "value", existing_type=mysql.VARCHAR(length=4096), type_=sa.String(length=8192), existing_nullable=False)
    op.alter_column("bw_services_settings", "value", existing_type=mysql.VARCHAR(length=4096), type_=sa.String(length=8192), existing_nullable=False)

    # Update all new columns in a single statement
    op.execute("UPDATE bw_ui_users SET is_two_factor_enabled = false, method = 'manual'")

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.5' WHERE id = 1")


def downgrade():
    # Revert changes to 'bw_ui_users'
    op.drop_constraint("uq_bw_ui_users_secret_token", "bw_ui_users", type_="unique")
    op.drop_column("bw_ui_users", "method")
    op.drop_column("bw_ui_users", "secret_token")
    op.drop_column("bw_ui_users", "is_two_factor_enabled")

    # Revert column sizes for VARCHAR
    op.alter_column("bw_global_values", "value", existing_type=sa.String(length=8192), type_=mysql.VARCHAR(length=4096), existing_nullable=False)
    op.alter_column("bw_services_settings", "value", existing_type=sa.String(length=8192), type_=mysql.VARCHAR(length=4096), existing_nullable=False)

    # Revert version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.4' WHERE id = 1")
