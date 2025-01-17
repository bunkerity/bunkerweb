"""Upgrade to version 1.6.0-rc2

Revision ID: 2f9f7600c78d
Revises: 6307fa627563
Create Date: 2025-01-15 16:18:37.077420

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2f9f7600c78d"
down_revision: Union[str, None] = "6307fa627563"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_selects", sa.Column("order", sa.Integer(), nullable=False))
    op.execute("SET @row_number = 0")
    op.execute(
        """
        UPDATE bw_selects
        SET `order` = (@row_number:=@row_number + 1)
        ORDER BY setting_id
    """
    )
    op.create_unique_constraint(None, "bw_selects", ["setting_id", "order"])

    # Update version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_constraint(None, "bw_selects", type_="unique")
    op.drop_column("bw_selects", "order")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc1' WHERE id = 1")
