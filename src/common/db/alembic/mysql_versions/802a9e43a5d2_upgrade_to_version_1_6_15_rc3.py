"""Upgrade to version 1.6.15~rc3

Revision ID: 802a9e43a5d2
Revises: d10f1615a002
Create Date: 2026-09-11 14:36:35.891058

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "802a9e43a5d2"
down_revision: Union[str, None] = "d10f1615a002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep retries safe after a partially applied non-transactional migration.
    offline = op.get_context().as_sql
    for table in ("bw_global_values", "bw_services_settings"):
        if offline or "is_draft" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column("is_draft", sa.Boolean(), server_default="0", nullable=False))
    # Record the new version only after the schema is ready.
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc3' WHERE id = 1")
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("Cannot downgrade individual setting drafts in offline mode; clear draft rows first")
    bind = op.get_bind()
    tables = [
        table for table in ("bw_services_settings", "bw_global_values") if "is_draft" in {column["name"] for column in sa.inspect(bind).get_columns(table)}
    ]
    # Dropping a draft flag would silently activate its retained value.
    for table in tables:
        if bind.execute(sa.text(f"SELECT 1 FROM {table} WHERE is_draft LIMIT 1")).first() is not None:
            raise RuntimeError(f"Cannot downgrade individual setting drafts while {table} contains draft rows; clear them first")
    for table in tables:
        op.drop_column(table, "is_draft")
    op.execute("UPDATE bw_metadata SET version = '1.6.15~rc2' WHERE id = 1")
