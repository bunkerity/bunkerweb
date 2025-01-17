"""Upgrade to version 1.5.2

Revision ID: 4a2457daed53
Revises: 3133d7320b63
Create Date: 2024-12-19 13:40:12.477741

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a2457daed53"
down_revision: Union[str, None] = "3133d7320b63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data migration: Update the version to 1.5.2
    op.execute("UPDATE bw_metadata SET version = '1.5.2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version back to 1.5.1
    op.execute("UPDATE bw_metadata SET version = '1.5.1' WHERE id = 1")
