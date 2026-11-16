"""`bw_ui_login_failures` carries exactly the schema dev shipped in 1.6.18~rc3.

The upgrade chain (QAR Q5) regenerates the 1.7 Alembic heads against dev's 1.6.18~rc3 schema: a 1.7
model that lacks this table, or that declares it differently, makes the generated head drop it or
alter it on the way up. The reference below is `class UserLoginFailures` copied verbatim from
`git show v1.6.18-rc3:src/common/db/model.py` (the 1.6 declarative `Column` style), compiled on a
private metadata. The 1.7 model uses `mapped_column`, so the two are compared where they have to
agree: the DDL each dialect would emit for the table and for every index.
"""

import pytest
from sqlalchemy import Column, DateTime, Identity, Integer, String
from sqlalchemy.dialects import mssql, mysql, oracle, postgresql, sqlite
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import CreateIndex, CreateTable

from model import Base


class _DevBase(DeclarativeBase):
    pass


class UserLoginFailures(_DevBase):  # verbatim from v1.6.18-rc3 src/common/db/model.py
    __tablename__ = "bw_ui_login_failures"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    # No foreign key on purpose: a failed login for an unknown username is counted too, so a lock never tells whether the user exists
    username = Column(String(256), nullable=False, index=True)
    ip = Column(String(45), nullable=False, index=True)
    failure_date = Column(DateTime(timezone=True), nullable=False, index=True)


DIALECTS = {"sqlite": sqlite, "postgresql": postgresql, "mysql": mysql, "oracle": oracle, "mssql": mssql}


def _mine():
    assert "bw_ui_login_failures" in Base.metadata.tables, "the 1.7 model has no bw_ui_login_failures table"
    return Base.metadata.tables["bw_ui_login_failures"]


def _ddl(table, dialect):
    statements = [str(CreateTable(table).compile(dialect=dialect.dialect()))]
    statements += [str(CreateIndex(index).compile(dialect=dialect.dialect())) for index in sorted(table.indexes, key=lambda index: index.name)]
    return "\n".join(statement.strip() for statement in statements)


@pytest.mark.parametrize("dialect", sorted(DIALECTS))
def test_the_ddl_is_identical_to_dev_on_every_dialect(dialect):
    assert _ddl(_mine(), DIALECTS[dialect]) == _ddl(UserLoginFailures.__table__, DIALECTS[dialect])


def test_columns_types_nullability_and_indexes_match_dev():
    mine, dev = _mine(), UserLoginFailures.__table__

    def shape(table):
        columns = {
            column.name: (
                type(column.type).__name__,
                getattr(column.type, "length", None),
                getattr(column.type, "timezone", None),
                column.nullable,
                column.primary_key,
            )
            for column in table.columns
        }
        indexes = sorted((index.name, tuple(column.name for column in index.columns), index.unique) for index in table.indexes)
        return (
            columns,
            indexes,
            sorted(table.foreign_keys, key=str),
            sorted(str(constraint) for constraint in table.constraints if constraint.__class__.__name__ == "UniqueConstraint"),
        )

    assert shape(mine) == shape(dev)
    assert not mine.foreign_keys  # on purpose: an unknown username is counted too
    identity = mine.c.id.identity
    assert (identity.start, identity.increment) == (1, 1)
