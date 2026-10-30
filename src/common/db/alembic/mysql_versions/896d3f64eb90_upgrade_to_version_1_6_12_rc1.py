"""Upgrade to version 1.6.12~rc1

Revision ID: 896d3f64eb90
Revises: a48eacc5e5b6
Create Date: 2026-05-29 14:49:38.522768

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "896d3f64eb90"
down_revision: Union[str, None] = "a48eacc5e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.12~rc1' WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.11' WHERE id = 1")
