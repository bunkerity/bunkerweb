"""Upgrade to version 1.6.0-rc2

Revision ID: b56eb8d8dbf2
Revises: 940350925f36
Create Date: 2025-01-15 16:26:12.567104

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b56eb8d8dbf2"
down_revision: Union[str, None] = "940350925f36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new order column to bw_selects
    # Step 1: Add column as nullable
    op.add_column("bw_selects", sa.Column("order", sa.Integer(), nullable=True))

    # Step 2: Populate default values
    op.execute(
        """
        UPDATE bw_selects
        SET "order" = subquery.row_number
        FROM (
            SELECT value, ROW_NUMBER() OVER (ORDER BY setting_id) as row_number
            FROM bw_selects
        ) as subquery
        WHERE bw_selects.value = subquery.value
    """
    )

    # Step 3: Alter column to NOT NULL
    op.alter_column("bw_selects", "order", nullable=False)

    # Step 4: Add unique constraint
    op.create_unique_constraint(None, "bw_selects", ["setting_id", "order"])

    # Check if status_new exists before renaming
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "status_new" in [col["name"] for col in inspector.get_columns("bw_instances")]:
        op.alter_column("bw_instances", "status_new", new_column_name="status")

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_constraint(None, "bw_selects", type_="unique")
    op.drop_column("bw_selects", "order")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc1' WHERE id = 1")
