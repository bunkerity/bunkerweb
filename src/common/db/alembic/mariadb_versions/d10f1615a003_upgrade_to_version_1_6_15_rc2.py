"""Upgrade to version 1.6.15~rc2

Revision ID: d10f1615a003
Revises: 581b304b1118
"""

from time import time
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d10f1615a003"
down_revision: Union[str, None] = "581b304b1118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Old installations predate API writes; keep every existing enum label and default.
    inspector = None if op.get_context().as_sql else sa.inspect(op.get_bind())
    for table in ("bw_custom_configs", "bw_global_values", "bw_instances", "bw_plugins", "bw_services", "bw_services_settings", "bw_ui_users"):
        column = (
            next(column for column in inspector.get_columns(table) if column["name"] == "method")
            if inspector is not None
            else {
                "type": sa.Enum("ui", "scheduler", "autoconf", "manual", "wizard"),
                "nullable": False,
                "default": "'manual'" if table in ("bw_plugins", "bw_ui_users") else None,
            }
        )
        if "api" not in column["type"].enums:
            op.alter_column(
                table,
                "method",
                existing_type=column["type"],
                type_=sa.Enum("api", *column["type"].enums, name="methods_enum"),
                existing_nullable=column["nullable"],
                existing_server_default=sa.text(column["default"]) if column["default"] is not None else None,
            )

    if op.get_context().as_sql or "totp_last_counter" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("bw_ui_users")}:
        op.add_column("bw_ui_users", sa.Column("totp_last_counter", sa.BigInteger(), nullable=True))
    # Local replay counters have no secret identifier and may already have been lost.
    # Expire all tokens valid before migration (30-second period, 3-second window).
    # Existing users can authenticate with the next fresh code, at most 33 seconds later.
    counter = int((time() + 3) // 30)
    op.execute(f"UPDATE bw_ui_users SET totp_last_counter = {counter} WHERE totp_secret IS NOT NULL AND totp_secret != '' AND totp_last_counter IS NULL")
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc2' WHERE id = 1")
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Keep API method support: the previous release already has API writers.
    op.drop_column("bw_ui_users", "totp_last_counter")
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc1' WHERE id = 1")
