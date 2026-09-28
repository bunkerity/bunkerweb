"""Normalize METRICS_REDIS_TTL count shorthand to seconds.

Revision ID: c63f7a0d5e42
Revises: 884ef6f96c44
Create Date: 2026-09-21
"""

from re import compile as re_compile
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c63f7a0d5e42"
down_revision: Union[str, None] = "884ef6f96c44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COUNT_SHORTHAND = re_compile(r"^(\d+)([kKmM])$")
_TABLES = (("bw_global_values", "value"), ("bw_services_settings", "value"), ("bw_template_settings", "default"))


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("Cannot normalize METRICS_REDIS_TTL in offline mode; run the migration online")
    bind = op.get_bind()
    for table, value_column in _TABLES:
        quoted_value = bind.dialect.identifier_preparer.quote(value_column)
        rows = bind.execute(sa.text(f"SELECT id, {quoted_value} AS value FROM {table} WHERE setting_id = 'METRICS_REDIS_TTL'"))
        for row in rows.mappings():
            match = _COUNT_SHORTHAND.fullmatch(str(row["value"]))
            if match:
                multiplier = 1000 if match.group(2).lower() == "k" else 1000000
                bind.execute(sa.text(f"UPDATE {table} SET {quoted_value} = :v WHERE id = :id"), {"id": row["id"], "v": str(int(match.group(1)) * multiplier)})


def downgrade() -> None:
    # Plain seconds satisfy the previous regex.
    pass
