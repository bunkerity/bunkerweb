"""Upgrade to version 1.6.2-rc4

Revision ID: d15ee0d0f93a
Revises: 111bd3f822da
Create Date: 2025-06-10 15:54:49.090205

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d15ee0d0f93a"
down_revision: Union[str, None] = "111bd3f822da"
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

    op.alter_column("bw_template_custom_configs", "step_id", existing_type=sa.INTEGER(), nullable=False)

    # Convert bw_ui_user_sessions.id from VARCHAR to INTEGER with explicit casting
    op.execute("ALTER TABLE bw_ui_user_sessions ALTER COLUMN id TYPE INTEGER USING id::integer")

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc4' WHERE id = 1")


def downgrade() -> None:
    op.alter_column("bw_template_custom_configs", "step_id", existing_type=sa.INTEGER(), nullable=True)
    op.create_unique_constraint(op.f("bw_settings_id_key"), "bw_settings", ["id"], postgresql_nulls_not_distinct=False)
    op.drop_table("bw_multiselects")

    # Convert bw_ui_user_sessions.id back to VARCHAR with explicit casting
    op.execute("ALTER TABLE bw_ui_user_sessions ALTER COLUMN id TYPE VARCHAR(256) USING id::varchar")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc3' WHERE id = 1")
