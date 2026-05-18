"""Upgrade to version 1.6.9~rc2

Revision ID: 7194d17b0717
Revises: ecbda0a804f1
Create Date: 2026-02-23 16:39:21.682269

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7194d17b0717"
down_revision: Union[str, None] = "ecbda0a804f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_global_values", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("bw_services_settings", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("bw_settings", sa.Column("accept", sa.String(length=512), nullable=True))
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc2' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_settings", "accept")
    op.drop_column("bw_services_settings", "file_name")
    op.drop_column("bw_global_values", "file_name")
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.9~rc1' WHERE id = 1")
