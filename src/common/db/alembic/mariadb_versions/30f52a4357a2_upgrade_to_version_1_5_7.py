"""Upgrade to version 1.5.7

Revision ID: 30f52a4357a2
Revises: 18e9d2191dcc
Create Date: 2024-12-17 10:19:55.586854

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "30f52a4357a2"
down_revision: Union[str, None] = "18e9d2191dcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new table for bw_cli_commands
    op.create_table(
        "bw_cli_commands",
        sa.Column("id", sa.Integer(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["bw_plugins.id"], onupdate="cascade", ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "name"),
    )

    # Handle foreign key constraints for bw_jobs_cache
    op.drop_constraint("fk_bw_jobs_cache_job_name", "bw_jobs_cache", type_="foreignkey")
    op.create_foreign_key(None, "bw_jobs_cache", "bw_jobs", ["job_name"], ["name"], onupdate="cascade", ondelete="cascade")

    # Add new columns to bw_plugin_pages
    op.add_column(
        "bw_plugin_pages",
        sa.Column("obfuscation_file", mysql.LONGBLOB(), nullable=True),
    )
    op.add_column(
        "bw_plugin_pages",
        sa.Column("obfuscation_checksum", sa.String(length=128), nullable=True),
    )

    # Add the new order column to bw_settings
    op.add_column("bw_settings", sa.Column("order", sa.Integer(), nullable=False))

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.7' WHERE id = 1")


def downgrade() -> None:
    # Reverse the version update
    op.execute("UPDATE bw_metadata SET version = '1.5.6' WHERE id = 1")

    # Reverse the addition of the order column
    op.drop_column("bw_settings", "order")

    # Reverse changes in bw_plugin_pages
    op.drop_column("bw_plugin_pages", "obfuscation_checksum")
    op.drop_column("bw_plugin_pages", "obfuscation_file")

    # Restore foreign key constraints for bw_jobs_cache
    op.drop_constraint(None, "bw_jobs_cache", type_="foreignkey")
    op.create_foreign_key("fk_bw_jobs_cache_job_name", "bw_jobs_cache", "bw_jobs", ["job_name"], ["name"])

    # Drop the newly created table bw_cli_commands
    op.drop_table("bw_cli_commands")

    # Revert the version update
    op.execute("UPDATE bw_metadata SET version = '1.5.6' WHERE id = 1")
