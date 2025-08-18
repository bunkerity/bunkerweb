"""Upgrade to version 1.6.4

Revision ID: cf17ba9f0d5f
Revises: 5eed3c0a192e
Create Date: 2025-08-18 09:35:48.420160

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "cf17ba9f0d5f"
down_revision: Union[str, None] = "5eed3c0a192e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.4' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3' WHERE id = 1")
