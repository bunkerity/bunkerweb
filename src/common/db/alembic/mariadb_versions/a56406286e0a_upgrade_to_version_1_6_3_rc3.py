"""Upgrade to version 1.6.3-rc3

Revision ID: a56406286e0a
Revises: fc5325200704
Create Date: 2025-07-30 10:38:56.712565

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a56406286e0a"
down_revision: Union[str, None] = "fc5325200704"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc3' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.6.3-rc2
    op.execute("UPDATE bw_metadata SET version = '1.6.3-rc2' WHERE id = 1")
