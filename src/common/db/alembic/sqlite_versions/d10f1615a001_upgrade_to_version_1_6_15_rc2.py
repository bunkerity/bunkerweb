"""Upgrade to version 1.6.15~rc2

Revision ID: d10f1615a001
Revises: 447a2b82a6c7
"""

from time import time
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d10f1615a001"
down_revision: Union[str, None] = "447a2b82a6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bw_ui_users", sa.Column("totp_last_counter", sa.BigInteger(), nullable=True))
    # Local replay counters have no secret identifier and may already have been lost.
    # Expire all tokens valid before migration (30-second period, 3-second window).
    # Existing users can authenticate with the next fresh code, at most 33 seconds later.
    counter = int((time() + 3) // 30)
    op.execute(f"UPDATE bw_ui_users SET totp_last_counter = {counter} WHERE totp_secret IS NOT NULL AND totp_secret != ''")
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc2' WHERE id = 1")
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    op.drop_column("bw_ui_users", "totp_last_counter")
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc1' WHERE id = 1")
