"""Upgrade to version 1.5.6

Revision ID: b4abd1acf9f1
Revises: 7deca2941c74
Create Date: 2024-12-19 13:49:55.657684

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4abd1acf9f1"
down_revision: Union[str, None] = "7deca2941c74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Create enums
    op.execute("CREATE TYPE pro_status_enum AS ENUM ('active', 'invalid', 'expired', 'suspended')")
    op.execute("CREATE TYPE plugin_types_enum AS ENUM ('core', 'external', 'pro')")
    op.execute("CREATE TYPE stream_types_enum AS ENUM ('no', 'yes', 'partial')")

    # Drop the foreign key constraint dynamically
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'bw_jobs_cache'::regclass
          AND confrelid = 'bw_jobs'::regclass
          AND conname LIKE '%_job_name%'
        """
        )
    ).fetchone()

    if result:
        constraint_name = result[0]
        with op.batch_alter_table("bw_jobs_cache") as batch_op:
            batch_op.drop_constraint(constraint_name, type_="foreignkey")

    # Drop index dynamically if it exists
    index_result = conn.execute(
        sa.text(
            """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'bw_jobs_cache'
          AND indexname = 'job_name'
        """
        )
    ).fetchone()

    if index_result:
        with op.batch_alter_table("bw_jobs_cache") as batch_op:
            batch_op.drop_index("job_name")

    # Add new foreign key
    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.create_foreign_key("fk_bw_jobs_cache_job_name", "bw_jobs", ["job_name"], ["name"])

    # Add new columns and alter existing ones
    op.add_column("bw_metadata", sa.Column("is_pro", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("bw_metadata", sa.Column("pro_expire", sa.DateTime(), nullable=True))
    op.add_column(
        "bw_metadata",
        sa.Column("pro_status", sa.Enum("active", "invalid", "expired", "suspended", name="pro_status_enum"), nullable=False, server_default="invalid"),
    )
    op.add_column("bw_metadata", sa.Column("pro_services", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bw_metadata", sa.Column("pro_overlapped", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("bw_metadata", sa.Column("last_pro_check", sa.DateTime(), nullable=True))
    op.add_column("bw_metadata", sa.Column("pro_plugins_changed", sa.Boolean(), nullable=True))

    op.add_column("bw_services", sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("bw_plugins", sa.Column("type", sa.Enum("core", "external", "pro", name="plugin_types_enum"), nullable=False, server_default="core"))

    # Alter the `stream` column with explicit casting
    op.execute(
        """
        ALTER TABLE bw_plugins
        ALTER COLUMN stream TYPE stream_types_enum
        USING stream::text::stream_types_enum
        """
    )

    # Migrate data: Set 'type' to 'external' where 'external' was true
    op.execute(
        """
        UPDATE bw_plugins
        SET type = 'external'
        WHERE external = true
    """
    )

    op.drop_column("bw_plugins", "external")

    op.alter_column("bw_global_values", "value", existing_type=sa.VARCHAR(length=8192), type_=sa.TEXT(), existing_nullable=False)
    op.alter_column("bw_services_settings", "value", existing_type=sa.VARCHAR(length=8192), type_=sa.TEXT(), existing_nullable=False)

    # Drop indices dynamically if they exist
    for table, index_name in (("bw_jobs", "name"), ("bw_settings", "name")):
        index_exists = conn.execute(
            sa.text(
                f"""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = '{table}'
                  AND indexname = '{index_name}'
                """
            )
        ).fetchone()

        if index_exists:
            op.drop_index(index_name, table_name=table)

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
    # Drop columns
    op.drop_column("bw_metadata", "pro_plugins_changed")
    op.drop_column("bw_metadata", "last_pro_check")
    op.drop_column("bw_metadata", "pro_overlapped")
    op.drop_column("bw_metadata", "pro_services")
    op.drop_column("bw_metadata", "pro_status")
    op.drop_column("bw_metadata", "pro_expire")
    op.drop_column("bw_metadata", "is_pro")

    op.drop_column("bw_services", "is_draft")

    op.add_column("bw_plugins", sa.Column("external", sa.Boolean(), autoincrement=False, nullable=False))

    # Migrate data: Set 'external' to true where 'type' was 'external'
    op.execute(
        """
        UPDATE bw_plugins
        SET external = true
        WHERE type = 'external'
    """
    )

    op.drop_column("bw_plugins", "type")

    # Revert the `stream` column back to VARCHAR
    op.execute(
        """
        ALTER TABLE bw_plugins
        ALTER COLUMN stream TYPE VARCHAR(16)
        USING stream::text
        """
    )

    op.alter_column(
        "bw_plugins", "stream", existing_type=sa.Enum("no", "yes", "partial", name="stream_types_enum"), type_=sa.VARCHAR(length=16), existing_nullable=False
    )
    op.alter_column("bw_global_values", "value", existing_type=sa.TEXT(), type_=sa.VARCHAR(length=8192), existing_nullable=False)
    op.alter_column("bw_services_settings", "value", existing_type=sa.TEXT(), type_=sa.VARCHAR(length=8192), existing_nullable=False)

    # Recreate indices
    op.create_index("name", "bw_jobs", ["name", "plugin_id"], unique=True)
    op.create_index("name", "bw_settings", ["name"], unique=True)

    # Drop the enum types
    op.execute("DROP TYPE IF EXISTS pro_status_enum")
    op.execute("DROP TYPE IF EXISTS plugin_types_enum")
    op.execute("DROP TYPE IF EXISTS stream_types_enum")

    # Recreate foreign key dynamically
    result = (
        op.get_bind()
        .execute(
            sa.text(
                """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'bw_jobs_cache'::regclass
          AND conname = 'fk_bw_jobs_cache_job_name'
        """
            )
        )
        .fetchone()
    )

    if result:
        with op.batch_alter_table("bw_jobs_cache") as batch_op:
            batch_op.drop_constraint("fk_bw_jobs_cache_job_name", type_="foreignkey")

    with op.batch_alter_table("bw_jobs_cache") as batch_op:
        batch_op.create_index("job_name", ["job_name", "service_id", "file_name"], unique=True)
        batch_op.create_foreign_key("bw_jobs_cache_ibfk_1", "bw_jobs", ["job_name"], ["name"])

    op.execute("UPDATE bw_metadata SET version = '1.5.5' WHERE id = 1")
