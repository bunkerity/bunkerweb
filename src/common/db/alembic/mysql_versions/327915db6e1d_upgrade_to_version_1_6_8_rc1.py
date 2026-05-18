"""Upgrade to version 1.6.8~rc1

Revision ID: 327915db6e1d
Revises: 65671c136899
Create Date: 2026-01-16 16:59:30.265811

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "327915db6e1d"
down_revision: Union[str, None] = "65671c136899"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("bw_global_values", "value", existing_type=mysql.TEXT(), type_=mysql.MEDIUMTEXT(), existing_nullable=True)
    op.alter_column("bw_services_settings", "value", existing_type=mysql.TEXT(), type_=mysql.MEDIUMTEXT(), existing_nullable=True)
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.8~rc1' WHERE id = 1")


def downgrade() -> None:
    op.alter_column("bw_services_settings", "value", existing_type=mysql.MEDIUMTEXT(), type_=mysql.TEXT(), existing_nullable=True)
    op.alter_column("bw_global_values", "value", existing_type=mysql.MEDIUMTEXT(), type_=mysql.TEXT(), existing_nullable=True)
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.7' WHERE id = 1")
