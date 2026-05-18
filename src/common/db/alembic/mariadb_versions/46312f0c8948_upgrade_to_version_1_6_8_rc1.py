"""Upgrade to version 1.6.8~rc1

Revision ID: 46312f0c8948
Revises: eef9dcb7dd1c
Create Date: 2026-01-16 16:53:19.210544

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "46312f0c8948"
down_revision: Union[str, None] = "eef9dcb7dd1c"
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
