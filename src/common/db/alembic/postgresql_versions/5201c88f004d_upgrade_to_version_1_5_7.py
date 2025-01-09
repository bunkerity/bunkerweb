"""Upgrade to version 1.5.7

Revision ID: 5201c88f004d
Revises: b4abd1acf9f1
Create Date: 2024-12-19 14:36:04.319448

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5201c88f004d"
down_revision: Union[str, None] = "b4abd1acf9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

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
    fk_result = conn.execute(
        sa.text(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'bw_jobs_cache'::regclass
              AND confrelid = 'bw_jobs'::regclass
              AND conname = 'fk_bw_jobs_cache_job_name'
            """
        )
    ).fetchone()

    if fk_result:
        op.drop_constraint("fk_bw_jobs_cache_job_name", "bw_jobs_cache", type_="foreignkey")

    op.create_foreign_key(None, "bw_jobs_cache", "bw_jobs", ["job_name"], ["name"], onupdate="cascade", ondelete="cascade")

    # Add new columns to bw_plugin_pages
    op.add_column("bw_plugin_pages", sa.Column("obfuscation_file", sa.LargeBinary(length=4294967295), nullable=True))
    op.add_column("bw_plugin_pages", sa.Column("obfuscation_checksum", sa.String(length=128), nullable=True))

    # Add the new order column to bw_settings
    # Step 1: Add column as nullable
    op.add_column("bw_settings", sa.Column("order", sa.Integer(), nullable=True))

    # Step 2: Populate default values
    op.execute('UPDATE bw_settings SET "order" = 0')

    # Step 3: Alter column to NOT NULL
    op.alter_column("bw_settings", "order", nullable=False)

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.5.7' WHERE id = 1")


def downgrade() -> None:
    conn = op.get_bind()

    # Reverse the version update
    op.execute("UPDATE bw_metadata SET version = '1.5.6' WHERE id = 1")

    # Reverse the addition of the order column
    op.drop_column("bw_settings", "order")

    # Reverse changes in bw_plugin_pages
    op.drop_column("bw_plugin_pages", "obfuscation_checksum")
    op.drop_column("bw_plugin_pages", "obfuscation_file")

    # Restore foreign key constraints for bw_jobs_cache
    fk_result = conn.execute(
        sa.text(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'bw_jobs_cache'::regclass
              AND confrelid = 'bw_jobs'::regclass
              AND conname IS NULL
            """
        )
    ).fetchone()

    if fk_result:
        op.drop_constraint(None, "bw_jobs_cache", type_="foreignkey")

    op.create_foreign_key("fk_bw_jobs_cache_job_name", "bw_jobs_cache", "bw_jobs", ["job_name"], ["name"])

    # Drop the newly created table bw_cli_commands
    op.drop_table("bw_cli_commands")
