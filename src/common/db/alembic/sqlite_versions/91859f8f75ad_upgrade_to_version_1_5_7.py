"""Upgrade to version 1.5.7

Revision ID: 91859f8f75ad
Revises: 0a4144dd55d4
Create Date: 2024-12-17 08:40:26.598223

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "91859f8f75ad"
down_revision: Union[str, None] = "0a4144dd55d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add 'order' column as nullable with a default
    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.add_column(sa.Column("order", sa.Integer(), nullable=True, server_default="0"))

    # Step 2: Set default value for existing rows
    op.execute("UPDATE bw_settings SET `order` = 0")

    # Step 3: Alter 'order' column to NOT NULL
    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column("order", nullable=False)

    # Add new columns to 'bw_plugin_pages'
    with op.batch_alter_table("bw_plugin_pages") as batch_op:
        batch_op.add_column(sa.Column("obfuscation_file", sa.LargeBinary(length=4294967295), nullable=True))
        batch_op.add_column(sa.Column("obfuscation_checksum", sa.String(length=128), nullable=True))

    # Create the new 'bw_cli_commands' table
    op.create_table(
        "bw_cli_commands",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["bw_plugins.id"], onupdate="cascade", ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "name"),
    )

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.7' WHERE id = 1")


def downgrade() -> None:
    # Drop the 'bw_cli_commands' table
    op.drop_table("bw_cli_commands")

    # Remove new columns from 'bw_plugin_pages'
    with op.batch_alter_table("bw_plugin_pages") as batch_op:
        batch_op.drop_column("obfuscation_checksum")
        batch_op.drop_column("obfuscation_file")

    # Drop 'order' column from 'bw_settings'
    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.drop_column("order")

    # Revert version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.6' WHERE id = 1")
