"""Dialect-level schema guards for the per-user KV table.

The default engine matrix is SQLite only (`tests/unit/README.md`), so nothing else in the
suite would notice a MySQL/MariaDB-specific DDL problem in this table until an install broke.
Compiling the DDL needs no server, so it runs everywhere.
"""

import pytest
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.schema import CreateTable

from model import UserPreferences  # type: ignore


def _ddl(dialect):
    return str(CreateTable(UserPreferences.__table__).compile(dialect=dialect))


def _mariadb():
    dialect = mysql.dialect()
    dialect.is_mariadb = True
    return dialect


@pytest.mark.parametrize("dialect", [mysql.dialect(), _mariadb()], ids=["mysql", "mariadb"])
def test_the_key_column_is_quoted_where_key_is_a_reserved_word(dialect):
    """`KEY` is reserved on MySQL and MariaDB. SQLAlchemy quotes it, but a hand-written
    `op.execute` in the pending rename migration would not — and unquoted DDL is a syntax
    error, so the install fails outright rather than degrading."""
    ddl = _ddl(dialect)

    assert "`key` VARCHAR(256) NOT NULL" in ddl
    assert "UNIQUE (user_name, `key`)" in ddl


def test_sqlite_quotes_it_too():
    assert '"key" VARCHAR(256) NOT NULL' in _ddl(sqlite.dialect())


def test_postgresql_needs_no_quoting():
    """`key` is non-reserved there; asserted so a future "just quote it everywhere" change
    is a deliberate one."""
    assert "key VARCHAR(256) NOT NULL" in _ddl(postgresql.dialect())


@pytest.mark.parametrize("dialect", [mysql.dialect(), _mariadb(), sqlite.dialect(), postgresql.dialect()], ids=["mysql", "mariadb", "sqlite", "postgresql"])
def test_the_uniqueness_is_on_user_plus_key_on_every_dialect(dialect):
    """One row per (user, key). Losing it lets a key exist twice and reads become arbitrary."""
    ddl = _ddl(dialect).lower()

    assert "unique (user_name, `key`)" in ddl or 'unique (user_name, "key")' in ddl or "unique (user_name, key)" in ddl
    assert "bw_ui_user_preferences" in ddl
