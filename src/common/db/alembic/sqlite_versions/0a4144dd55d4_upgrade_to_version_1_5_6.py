"""Upgrade to version 1.5.6

Revision ID: 0a4144dd55d4
Revises: c9586782cd77
Create Date: 2024-12-17 08:39:34.882278

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0a4144dd55d4"
down_revision: Union[str, None] = "c9586782cd77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define Enums for consistency
PRO_STATUS_ENUM = sa.Enum("active", "invalid", "expired", "suspended", name="pro_status_enum")
PLUGIN_TYPES_ENUM = sa.Enum("core", "external", "pro", name="plugin_types_enum")
STREAM_TYPES_ENUM = sa.Enum("no", "yes", "partial", name="stream_types_enum")


def upgrade():
    # Alter value columns to TEXT in bw_global_values and bw_services_settings
    with op.batch_alter_table("bw_global_values") as batch_op:
        batch_op.alter_column("value", type_=sa.TEXT(), existing_type=sa.VARCHAR(length=8192))

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.alter_column("value", type_=sa.TEXT(), existing_type=sa.VARCHAR(length=8192))

    # Add new columns to bw_metadata
    op.add_column("bw_metadata", sa.Column("is_pro", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("bw_metadata", sa.Column("pro_expire", sa.DateTime(), nullable=True))
    op.add_column("bw_metadata", sa.Column("pro_status", PRO_STATUS_ENUM, nullable=False, server_default="invalid"))
    op.add_column("bw_metadata", sa.Column("pro_services", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bw_metadata", sa.Column("pro_overlapped", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("bw_metadata", sa.Column("last_pro_check", sa.DateTime(), nullable=True))
    op.add_column("bw_metadata", sa.Column("pro_plugins_changed", sa.Boolean(), nullable=True))

    # Modify bw_plugins table
    # Step 1: Add the new 'type' column with default 'external'
    op.add_column("bw_plugins", sa.Column("type", PLUGIN_TYPES_ENUM, nullable=False, server_default="core"))

    # Step 2: Migrate data: Set 'type' to 'external' where 'external' was true
    op.execute(
        """
        UPDATE bw_plugins
        SET type = 'external'
        WHERE external = true
    """
    )

    # Step 3: Drop the 'external' column and alter the 'stream' column to STREAM_TYPES_ENUM
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.drop_column("external")
        batch_op.alter_column("stream", type_=STREAM_TYPES_ENUM, existing_type=sa.VARCHAR(length=16))

    # Add is_draft column to bw_services
    op.add_column("bw_services", sa.Column("is_draft", sa.Boolean(), nullable=False, server_default="0"))

    # Update all new columns and version in a single statement
    op.execute(
        """
        UPDATE bw_metadata
        SET is_pro = false,
            pro_status = 'invalid',
            pro_services = 0,
            pro_overlapped = false,
            pro_plugins_changed = false,
            version = '1.5.6'
        WHERE id = 1
    """
    )


def downgrade():
    # Revert changes in bw_services
    op.drop_column("bw_services", "is_draft")

    # Revert changes in bw_plugins
    with op.batch_alter_table("bw_plugins") as batch_op:
        batch_op.add_column(sa.Column("external", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.alter_column("stream", type_=sa.VARCHAR(length=16), existing_type=STREAM_TYPES_ENUM)

    # Migrate data: Set 'type' to 'external' where 'external' was true
    op.execute(
        """
        UPDATE bw_plugins
        SET external = true
        WHERE type = 'external'
    """
    )

    # Drop new columns from bw_plugins
    op.drop_column("bw_plugins", "type")

    # Drop new columns from bw_metadata
    op.drop_column("bw_metadata", "pro_plugins_changed")
    op.drop_column("bw_metadata", "last_pro_check")
    op.drop_column("bw_metadata", "pro_overlapped")
    op.drop_column("bw_metadata", "pro_services")
    op.drop_column("bw_metadata", "pro_status")
    op.drop_column("bw_metadata", "pro_expire")
    op.drop_column("bw_metadata", "is_pro")

    # Revert value columns in bw_global_values and bw_services_settings
    with op.batch_alter_table("bw_global_values") as batch_op:
        batch_op.alter_column("value", type_=sa.VARCHAR(length=8192), existing_type=sa.TEXT())

    with op.batch_alter_table("bw_services_settings") as batch_op:
        batch_op.alter_column("value", type_=sa.VARCHAR(length=8192), existing_type=sa.TEXT())

    # Revert version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.5' WHERE id = 1")
