"""Shared DB-construction helper used by the engine-parametrized fixtures.

Kept separate from ``conftest.py`` so the root ``db`` fixture and the API/UI subdir
fixtures can all reuse the same engine resolution + skip logic without importing each
other's conftest.
"""

import os

import pytest

from fixtures.engines import ENGINE_ENV, build_sqlite_uri, env_uri, is_reachable


def resolve_uri(db_engine, tmp_path):
    """Return a usable URI for ``db_engine``, or ``pytest.skip`` if it's unavailable."""
    if db_engine == "sqlite":
        return build_sqlite_uri(tmp_path)
    uri = env_uri(db_engine, os.environ)
    if not uri:
        pytest.skip(f"{db_engine} not configured (set {ENGINE_ENV[db_engine]})")
    if not is_reachable(uri):
        pytest.skip(f"{db_engine} not reachable at {uri}")
    return uri
