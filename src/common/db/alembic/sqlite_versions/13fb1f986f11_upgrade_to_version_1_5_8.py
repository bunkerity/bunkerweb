"""Upgrade to version 1.5.8

Revision ID: 13fb1f986f11
Revises: 91859f8f75ad
Create Date: 2024-12-17 08:41:34.664880

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "13fb1f986f11"
down_revision: Union[str, None] = "91859f8f75ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to 'bw_metadata'
    with op.batch_alter_table("bw_metadata") as batch_op:
        batch_op.add_column(sa.Column("pro_license", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("last_custom_configs_change", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_external_plugins_change", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_pro_plugins_change", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_instances_change", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("failover", sa.Boolean(), nullable=True))
        batch_op.drop_column("config_changed")

    # Add new columns to 'bw_plugins'
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.add_column(sa.Column("config_changed", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("last_config_change", sa.DateTime(), nullable=True))

    # Set default value for 'config_changed' in 'bw_plugins'
    op.execute("UPDATE bw_plugins SET config_changed = false")

    # Update version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.8' WHERE id = 1")


def downgrade() -> None:
    # Revert 'bw_plugins' changes
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.drop_column("last_config_change")
        batch_op.drop_column("config_changed")

    # Revert 'bw_metadata' changes
    with op.batch_alter_table("bw_metadata") as batch_op:
        batch_op.add_column(sa.Column("config_changed", sa.Boolean(), nullable=True))
        batch_op.drop_column("failover")
        batch_op.drop_column("last_instances_change")
        batch_op.drop_column("last_pro_plugins_change")
        batch_op.drop_column("last_external_plugins_change")
        batch_op.drop_column("last_custom_configs_change")
        batch_op.drop_column("pro_license")

    # Revert version in 'bw_metadata'
    op.execute("UPDATE bw_metadata SET version = '1.5.7', config_changed = false WHERE id = 1")
