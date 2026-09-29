"""Add comment column to bw_services.

Revision ID: e8a1c3f49b10
Revises: 5005ba753754
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8a1c3f49b10"
down_revision: Union[str, None] = "5005ba753754"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_context().as_sql or "comment" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("bw_services")}:
        op.add_column("bw_services", sa.Column("comment", sa.Text(), nullable=True))


def downgrade() -> None:
    if op.get_context().as_sql or "comment" in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("bw_services")}:
        op.drop_column("bw_services", "comment")
