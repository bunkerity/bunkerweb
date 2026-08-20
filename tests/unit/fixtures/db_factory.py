"""Shared DB-construction helper used by the engine-parametrized fixtures.

Kept separate from ``conftest.py`` so the root ``db`` fixture and the API/UI subdir
fixtures can all reuse the same engine resolution + skip logic without importing each
other's conftest.
"""

import os

import pytest

from fixtures.engines import ENGINE_ENV, build_sqlite_uri, env_uri, is_reachable


def resolve_uri(db_engine, tmp_path):
    """Return the configured URI for ``db_engine``, or ``pytest.skip`` if it's unavailable.

    The URI is returned **as configured**, which for PostgreSQL and MariaDB means without a DBAPI
    driver: ``postgresql://...`` and ``mariadb://...`` as documented in ``tests/unit/README.md``.
    SQLAlchemy cannot open either as-is — it defaults them to ``psycopg2`` and ``MySQLdb``, and
    BunkerWeb ships neither. Every consumer supplies the driver downstream instead: ``reset_schema``
    through ``engines._with_driver``, and ``Database`` through its own injection at
    ``Database.py:184-196``. A new caller that hands this string straight to SQLAlchemy or to alembic
    will get ``ModuleNotFoundError`` and should call ``engines._with_driver`` first, exactly as
    ``scheduler/entrypoint.sh:83-99`` re-exports the driver-injected URI before running alembic.
    """
    if db_engine == "sqlite":
        return build_sqlite_uri(tmp_path)
    uri = env_uri(db_engine, os.environ)
    if not uri:
        pytest.skip(f"{db_engine} not configured (set {ENGINE_ENV[db_engine]})")
    if not is_reachable(uri):
        pytest.skip(f"{db_engine} not reachable at {uri}")
    return uri
