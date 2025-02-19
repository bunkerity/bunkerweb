"""Upgrade to version 1.6.1-rc1

Revision ID: 864a1dbd2430
Revises: c1dc539b9d02
Create Date: 2025-02-19 13:27:26.139343

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "864a1dbd2430"
down_revision: Union[str, None] = "c1dc539b9d02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.1-rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.0' WHERE id = 1")
