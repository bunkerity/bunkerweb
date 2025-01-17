"""Upgrade to version 1.6.0-rc2

Revision ID: 92038d1e365e
Revises: 5b0ea031ccfc
Create Date: 2025-01-15 15:55:16.757661

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "92038d1e365e"
down_revision: Union[str, None] = "5b0ea031ccfc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bw_selects") as batch_op:
        batch_op.add_column(sa.Column("order", sa.Integer(), nullable=False, server_default="0"))
    # Assign unique order values within each setting_id group
    op.execute(
        """
        UPDATE bw_selects SET "order" = (
            SELECT COUNT(*) - 1
            FROM bw_selects s2
            WHERE s2.setting_id = bw_selects.setting_id
            AND s2.rowid <= bw_selects.rowid
        )
    """
    )
    with op.batch_alter_table("bw_selects") as batch_op:
        batch_op.create_unique_constraint("uq_setting_order", ["setting_id", "order"])

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc2' WHERE id = 1")


def downgrade() -> None:
    with op.batch_alter_table("bw_selects") as batch_op:
        batch_op.drop_constraint("uq_setting_order", type_="unique")
        batch_op.drop_column("order")
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc1' WHERE id = 1")
