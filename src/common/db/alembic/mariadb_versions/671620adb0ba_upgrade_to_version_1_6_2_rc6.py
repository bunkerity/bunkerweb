"""Upgrade to version 1.6.2-rc6

Revision ID: 671620adb0ba
Revises: ce73d5bafffd
Create Date: 2025-06-18 07:16:51.276397

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "671620adb0ba"
down_revision: Union[str, None] = "ce73d5bafffd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc6' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.2-rc5' WHERE id = 1")
