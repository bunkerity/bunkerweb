"""Upgrade to version 1.5.5

Revision ID: c9586782cd77
Revises: 17a6fddfddc2
Create Date: 2024-12-17 08:38:08.728703

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9586782cd77"
down_revision: Union[str, None] = "17a6fddfddc2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


METHODS_ENUM = sa.Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum")


def upgrade():
    # Add new columns to bw_ui_users
    with op.batch_alter_table("bw_ui_users") as batch_op:
        batch_op.add_column(sa.Column("is_two_factor_enabled", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("secret_token", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("method", METHODS_ENUM, nullable=False, server_default="manual"))

    # Create unique constraint on bw_ui_users
    with op.batch_alter_table("bw_ui_users") as batch_op:
        batch_op.create_unique_constraint("uq_bw_ui_users_secret_token", ["secret_token"])

    # Alter column lengths in bw_global_values and bw_services_settings
    with op.batch_alter_table("bw_global_values") as batch_op:
        batch_op.alter_column("value", type_=sa.String(8192), existing_type=sa.String(4096))

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.alter_column("value", type_=sa.String(8192), existing_type=sa.String(4096))

    # Update all new columns in a single statement
    op.execute("UPDATE bw_ui_users SET is_two_factor_enabled = false, method = 'manual'")

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.5' WHERE id = 1")


def downgrade():
    # Revert bw_ui_users changes
    with op.batch_alter_table("bw_ui_users") as batch_op:
        batch_op.drop_constraint("uq_bw_ui_users_secret_token", type_="unique")
        batch_op.drop_column("method")
        batch_op.drop_column("secret_token")
        batch_op.drop_column("is_two_factor_enabled")

    # Revert column lengths in bw_global_values and bw_services_settings
    with op.batch_alter_table("bw_global_values") as batch_op:
        batch_op.alter_column("value", type_=sa.String(4096), existing_type=sa.String(8192))

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.alter_column("value", type_=sa.String(4096), existing_type=sa.String(8192))

    # Revert version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.4' WHERE id = 1")
