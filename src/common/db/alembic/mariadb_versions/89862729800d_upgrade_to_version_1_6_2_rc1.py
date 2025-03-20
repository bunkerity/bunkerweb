"""Upgrade to version 1.6.2-rc1

Revision ID: 89862729800d
Revises: 956a842dde27
Create Date: 2025-03-20 13:15:40.895020

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "89862729800d"
down_revision: Union[str, None] = "956a842dde27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_global_values", sa.Column("id", sa.Integer(), autoincrement=True, nullable=False))
    op.alter_column("bw_global_values", "value", existing_type=mysql.TEXT(), nullable=True)
    op.alter_column("bw_global_values", "suffix", existing_type=mysql.INTEGER(display_width=11), nullable=True)
    op.create_unique_constraint(None, "bw_global_values", ["setting_id", "suffix"])
    op.add_column("bw_selects", sa.Column("id", sa.Integer(), autoincrement=True, nullable=False))
    op.alter_column("bw_selects", "value", existing_type=mysql.VARCHAR(length=256), nullable=True)
    op.create_unique_constraint(None, "bw_selects", ["setting_id", "value"])
    op.add_column("bw_services_settings", sa.Column("id", sa.Integer(), autoincrement=True, nullable=False))
    op.alter_column("bw_services_settings", "value", existing_type=mysql.TEXT(), nullable=True)
    op.alter_column("bw_services_settings", "suffix", existing_type=mysql.INTEGER(display_width=11), nullable=True)
    op.create_unique_constraint(None, "bw_services_settings", ["service_id", "setting_id", "suffix"])
    op.alter_column("bw_template_custom_configs", "step_id", existing_type=mysql.INTEGER(display_width=11), nullable=False)
    op.alter_column("bw_template_settings", "step_id", existing_type=mysql.INTEGER(display_width=11), nullable=False)
    op.alter_column("bw_template_settings", "default", existing_type=mysql.TEXT(), nullable=True)
    op.alter_column("bw_ui_user_sessions", "user_agent", existing_type=mysql.TEXT(), nullable=True)

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc1' WHERE id = 1")


def downgrade() -> None:
    op.alter_column("bw_ui_user_sessions", "user_agent", existing_type=mysql.TEXT(), nullable=False)
    op.alter_column("bw_template_settings", "default", existing_type=mysql.TEXT(), nullable=False)
    op.alter_column("bw_template_settings", "step_id", existing_type=mysql.INTEGER(display_width=11), nullable=True)
    op.alter_column("bw_template_custom_configs", "step_id", existing_type=mysql.INTEGER(display_width=11), nullable=True)
    op.drop_constraint(None, "bw_services_settings", type_="unique")
    op.alter_column("bw_services_settings", "suffix", existing_type=mysql.INTEGER(display_width=11), nullable=False)
    op.alter_column("bw_services_settings", "value", existing_type=mysql.TEXT(), nullable=False)
    op.drop_column("bw_services_settings", "id")
    op.drop_constraint(None, "bw_selects", type_="unique")
    op.alter_column("bw_selects", "value", existing_type=mysql.VARCHAR(length=256), nullable=False)
    op.drop_column("bw_selects", "id")
    op.drop_constraint(None, "bw_global_values", type_="unique")
    op.alter_column("bw_global_values", "suffix", existing_type=mysql.INTEGER(display_width=11), nullable=False)
    op.alter_column("bw_global_values", "value", existing_type=mysql.TEXT(), nullable=False)
    op.drop_column("bw_global_values", "id")

    # Revert version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.6.1', config_changed = false WHERE id = 1")
