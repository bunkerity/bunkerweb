"""Upgrade to version 1.5.3

Revision ID: e9b703e3d747
Revises: 4a2457daed53
Create Date: 2024-12-19 13:41:11.126097

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e9b703e3d747"
down_revision: Union[str, None] = "4a2457daed53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data migration: Update the version to 1.5.3
    op.execute("UPDATE bw_metadata SET version = '1.5.3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version back to 1.5.2
    op.execute("UPDATE bw_metadata SET version = '1.5.2' WHERE id = 1")
