"""Upgrade to version 1.5.12

Revision ID: fbd680c6ffeb
Revises: efb577b1c25d
Create Date: 2024-12-19 14:46:13.313028

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fbd680c6ffeb"
down_revision: Union[str, None] = "efb577b1c25d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update version to 1.5.12
    op.execute("UPDATE bw_metadata SET version = '1.5.12' WHERE id = 1")


def downgrade() -> None:
    # Revert version to 1.5.11
    op.execute("UPDATE bw_metadata SET version = '1.5.11' WHERE id = 1")
