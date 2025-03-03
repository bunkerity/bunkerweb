"""Upgrade to version 1.6.1-rc3

Revision ID: bb22be303c00
Revises: 07f8fe23ccb5
Create Date: 2025-03-03 14:58:09.042013

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bb22be303c00"
down_revision: Union[str, None] = "07f8fe23ccb5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bw_ui_user_columns_preferences") as batch_op:
        batch_op.alter_column("table_name", existing_type=sa.VARCHAR(length=9), type_=sa.String(length=256), existing_nullable=False)

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc3' WHERE id = 1")


def downgrade() -> None:
    with op.batch_alter_table("bw_ui_user_columns_preferences") as batch_op:
        batch_op.alter_column("table_name", existing_type=sa.String(length=256), type_=sa.VARCHAR(length=9), existing_nullable=False)

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc2' WHERE id = 1")
