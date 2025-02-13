"""Upgrade to version 1.6.0

Revision ID: c1dc539b9d02
Revises: 927114675a7d
Create Date: 2025-02-13 10:04:39.747963

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c1dc539b9d02"
down_revision: Union[str, None] = "927114675a7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0-rc4' WHERE id = 1")
