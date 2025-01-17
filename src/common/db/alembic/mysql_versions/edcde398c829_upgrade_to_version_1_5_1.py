"""Upgrade to version 1.5.1

Revision ID: edcde398c829
Revises: 41d395e48cfd
Create Date: 2024-12-19 13:16:34.086006

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "edcde398c829"
down_revision: Union[str, None] = "41d395e48cfd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new columns to bw_metadata."""
    with op.batch_alter_table("bw_metadata") as batch_op:
        batch_op.add_column(sa.Column("scheduler_first_start", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("custom_configs_changed", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("external_plugins_changed", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("config_changed", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("instances_changed", sa.Boolean(), nullable=True))

    # Update all new columns and version in a single statement
    op.execute(
        """
        UPDATE bw_metadata
        SET scheduler_first_start = false,
            custom_configs_changed = false,
            external_plugins_changed = false,
            config_changed = false,
            instances_changed = false,
            version = '1.5.1'
        WHERE id = 1
    """
    )


def downgrade() -> None:
    """Remove new columns from bw_metadata."""
    with op.batch_alter_table("bw_metadata") as batch_op:
        batch_op.drop_column("instances_changed")
        batch_op.drop_column("config_changed")
        batch_op.drop_column("external_plugins_changed")
        batch_op.drop_column("custom_configs_changed")
        batch_op.drop_column("scheduler_first_start")

    # Revert the version back to 1.5.0
    op.execute("UPDATE bw_metadata SET version = '1.5.0' WHERE id = 1")
