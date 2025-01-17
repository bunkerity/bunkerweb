"""Upgrade to version 1.5.2

Revision ID: 24e08b364fa1
Revises: cc61497f1976
Create Date: 2024-12-17 10:19:39.901086

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "24e08b364fa1"
down_revision: Union[str, None] = "cc61497f1976"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data migration: Update the version to 1.5.2
    op.execute("UPDATE bw_metadata SET version = '1.5.2' WHERE id = 1")


def downgrade() -> None:
    # Revert the version back to 1.5.1
    op.execute("UPDATE bw_metadata SET version = '1.5.1' WHERE id = 1")
