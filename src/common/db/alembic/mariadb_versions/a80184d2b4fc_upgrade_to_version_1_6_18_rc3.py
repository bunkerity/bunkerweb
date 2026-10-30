"""Upgrade to version 1.6.18~rc3

Revision ID: a80184d2b4fc
Revises: 5462f610384b
Create Date: 2026-10-29 17:26:07.835122

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a80184d2b4fc"
down_revision: Union[str, None] = "5462f610384b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.18~rc3' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")
    # init_tables' create_all may already have created it on a dev or testing database
    if not sa.inspect(op.get_bind()).has_table("bw_ui_login_failures"):
        op.create_table(
            "bw_ui_login_failures",
            sa.Column("id", sa.Integer(), sa.Identity(always=False, start=1, increment=1), nullable=False),
            sa.Column("username", sa.String(length=256), nullable=False),
            sa.Column("ip", sa.String(length=45), nullable=False),
            sa.Column("failure_date", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_bw_ui_login_failures_username"), "bw_ui_login_failures", ["username"], unique=False)
        op.create_index(op.f("ix_bw_ui_login_failures_ip"), "bw_ui_login_failures", ["ip"], unique=False)
        op.create_index(op.f("ix_bw_ui_login_failures_failure_date"), "bw_ui_login_failures", ["failure_date"], unique=False)


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.18~rc2' WHERE id = 1")
    op.drop_table("bw_ui_login_failures")
