"""Upgrade to version 1.5.3

Revision ID: c38183e63472
Revises: 24e08b364fa1
Create Date: 2024-12-17 10:19:43.986783

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "c38183e63472"
down_revision: Union[str, None] = "24e08b364fa1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data migration: Update the version to 1.5.3
    op.execute("UPDATE bw_metadata SET version = '1.5.3' WHERE id = 1")


def downgrade() -> None:
    # Revert the version back to 1.5.2
    op.execute("UPDATE bw_metadata SET version = '1.5.2' WHERE id = 1")
