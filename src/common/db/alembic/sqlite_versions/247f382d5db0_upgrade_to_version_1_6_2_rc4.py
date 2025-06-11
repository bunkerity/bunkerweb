"""Upgrade to version 1.6.2-rc4

Revision ID: 247f382d5db0
Revises: 6963ee773ffc
Create Date: 2025-06-10 15:38:38.685165

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "247f382d5db0"
down_revision: Union[str, None] = "6963ee773ffc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bw_multiselects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setting_id", sa.String(length=256), nullable=False),
        sa.Column("option_id", sa.String(length=256), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["setting_id"], ["bw_settings.id"], onupdate="cascade", ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setting_id", "option_id"),
        sa.UniqueConstraint("setting_id", "order"),
    )

    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column("type", existing_type=sa.String(length=8), type_=sa.String(length=11), existing_nullable=False)

    with op.batch_alter_table("bw_ui_user_sessions") as batch_op:
        batch_op.alter_column("id", existing_type=sa.String(length=256), type_=sa.Integer(), existing_nullable=False, autoincrement=True)

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc4' WHERE id = 1")


def downgrade() -> None:
    with op.batch_alter_table("bw_ui_user_sessions") as batch_op:
        batch_op.alter_column("id", existing_type=sa.Integer(), type_=sa.String(length=256), existing_nullable=False, autoincrement=True)

    with op.batch_alter_table("bw_settings") as batch_op:
        batch_op.alter_column("type", existing_type=sa.String(length=11), type_=sa.String(length=8), existing_nullable=False)

    op.drop_table("bw_multiselects")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc3' WHERE id = 1")
