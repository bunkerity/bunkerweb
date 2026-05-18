"""Upgrade to version 1.6.9~rc2

Revision ID: 7b000e03cdcd
Revises: 7ff687d13019
Create Date: 2026-02-23 16:45:38.185279

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "7b000e03cdcd"
down_revision: Union[str, None] = "7ff687d13019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'file' to the settings_types_enum
    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=mysql.ENUM("password", "text", "number", "check", "select", "multiselect", "multivalue"),
            type_=mysql.ENUM("password", "text", "number", "file", "check", "select", "multiselect", "multivalue"),
            existing_nullable=False,
        )

    op.add_column("bw_global_values", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("bw_services_settings", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("bw_settings", sa.Column("accept", sa.String(length=512), nullable=True))
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_settings", "accept")
    op.drop_column("bw_services_settings", "file_name")
    op.drop_column("bw_global_values", "file_name")

    # Remove 'file' from the settings_types_enum
    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=mysql.ENUM("password", "text", "number", "file", "check", "select", "multiselect", "multivalue"),
            type_=mysql.ENUM("password", "text", "number", "check", "select", "multiselect", "multivalue"),
            existing_nullable=False,
        )

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc1' WHERE id = 1")
