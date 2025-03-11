"""Upgrade to version 1.6.1

Revision ID: 956a842dde27
Revises: 77f5538f2b7e
Create Date: 2025-03-10 08:27:57.248530

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "956a842dde27"
down_revision: Union[str, None] = "77f5538f2b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_metadata", sa.Column("failover_message", sa.TEXT(), nullable=True))

    op.execute("UPDATE bw_plugins SET type = 'core', data = NULL, checksum = NULL WHERE id = 'crowdsec' AND type = 'external'")

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_metadata", "failover_message")

    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc3' WHERE id = 1")
