"""Upgrade to version 1.6.16~rc2

Revision ID: f39324749273
Revises: 3257b41568d0
Create Date: 2026-09-25 18:51:38.092866

"""

from re import compile as re_compile
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "f39324749273"
down_revision: Union[str, None] = "3257b41568d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COUNT_SHORTHAND = re_compile(r"^(\d+)([kKmM])$")
_TABLES = (("bw_global_values", "value"), ("bw_services_settings", "value"), ("bw_template_settings", "default"))


def upgrade() -> None:
    # Normalize METRICS_REDIS_TTL count shorthand (e.g. 10k) to seconds
    if op.get_context().as_sql:
        raise RuntimeError("Cannot normalize METRICS_REDIS_TTL in offline mode; run the migration online")
    bind = op.get_bind()
    for table, value_column in _TABLES:
        quoted_value = bind.dialect.identifier_preparer.quote(value_column)
        rows = bind.execute(text(f"SELECT id, {quoted_value} AS value FROM {table} WHERE setting_id = 'METRICS_REDIS_TTL'"))
        for row in rows.mappings():
            match = _COUNT_SHORTHAND.fullmatch(str(row["value"]))
            if match:
                multiplier = 1000 if match.group(2).lower() == "k" else 1000000
                bind.execute(text(f"UPDATE {table} SET {quoted_value} = :v WHERE id = :id"), {"id": row["id"], "v": str(int(match.group(1)) * multiplier)})

    # Update the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16~rc2' WHERE id = 1")
    # Force a Pro plugins re-check after the version change
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")


def downgrade() -> None:
    # Revert the version in bw_metadata
    op.execute("UPDATE bw_metadata SET version = '1.6.16~rc1' WHERE id = 1")
