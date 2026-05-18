"""Upgrade to version 1.6.9~rc2

Revision ID: 32d89d02c8e5
Revises: ac4c8572cc1f
Create Date: 2026-02-23 16:50:24.338868

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "32d89d02c8e5"
down_revision: Union[str, None] = "ac4c8572cc1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'file' to the settings_types_enum
    op.execute("ALTER TYPE settings_types_enum ADD VALUE IF NOT EXISTS 'file' AFTER 'number'")

    op.add_column("bw_global_values", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("bw_services_settings", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("bw_settings", sa.Column("accept", sa.String(length=512), nullable=True))
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_settings", "accept")
    op.drop_column("bw_services_settings", "file_name")
    op.drop_column("bw_global_values", "file_name")
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc1' WHERE id = 1")
