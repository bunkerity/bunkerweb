"""Upgrade to version 1.6.16~rc3

Revision ID: ec30a1469cb0
Revises: 7b7a101de004
Create Date: 2026-09-30 12:08:09.033720

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ec30a1469cb0"
down_revision: Union[str, None] = "7b7a101de004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16~rc3' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")
    # init_tables' create_all may already have created it on a dev or testing database
    if not sa.inspect(op.get_bind()).has_table("bw_blob_chunks"):
        op.create_table(
            "bw_blob_chunks",
            sa.Column("owner", sa.String(length=128), nullable=False),
            sa.Column("checksum", sa.String(length=64), nullable=False),
            sa.Column("idx", sa.Integer(), autoincrement=False, nullable=False),
            sa.Column("data", sa.LargeBinary(length=4294967295), nullable=False),
            sa.PrimaryKeyConstraint("owner", "checksum", "idx"),
        )


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16~rc2' WHERE id = 1")
    op.drop_table("bw_blob_chunks")
