"""Shared pytest configuration and fixtures for the BunkerWeb unit-test suite.

Responsibilities:
  * inject the ``src/common/db`` (+utils/api) directories onto ``sys.path`` before
    any test imports ``Database``/``model`` (bare-import layout — see ``_paths``);
  * expose a ``--db-engines`` option (default ``sqlite``) and parametrize the ``db``
    fixture across the selected engines (SQLite / PostgreSQL / MariaDB);
  * build a ready, schema-reset ``Database`` per test with per-test isolation;
  * keep the developer's shell env from perturbing tests.
"""

import logging
import os
import sys
from pathlib import Path

import pytest

# --- sys.path injection (must run before importing Database/model/fixtures) -------
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _paths import DB_LAYER_PATHS, inject  # noqa: E402

inject(DB_LAYER_PATHS)

from fixtures.engines import reset_schema  # noqa: E402
from fixtures.db_factory import resolve_uri  # noqa: E402

DEFAULT_ENGINE = "sqlite"
ALL_ENGINES = ("sqlite", "postgresql", "mariadb")


# --- engine selection -------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        "--db-engines",
        action="store",
        default=None,
        help="Comma-separated DB engines for DB tests: sqlite,postgresql,mariadb " "(default: sqlite). Overrides the BW_TEST_DB_ENGINES env var.",
    )


def _selected_engines(config):
    raw = config.getoption("--db-engines") or os.getenv("BW_TEST_DB_ENGINES") or DEFAULT_ENGINE
    engines = [e.strip() for e in raw.split(",") if e.strip()]
    bad = [e for e in engines if e not in ALL_ENGINES]
    if bad:
        raise pytest.UsageError(f"Unknown --db-engines values {bad}; valid choices are {ALL_ENGINES}")
    return engines


def pytest_generate_tests(metafunc):
    """Parametrize every test that consumes the ``db`` fixture across the selected engines."""
    if "db_engine" in metafunc.fixturenames:
        metafunc.parametrize("db_engine", _selected_engines(metafunc.config), ids=lambda e: e)


# --- environment & logging --------------------------------------------------------
@pytest.fixture(scope="session")
def quiet_logger():
    """A silent stdlib logger for the Database constructor (which requires one)."""
    logger = logging.getLogger("bw-unit-test")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False
    return logger


@pytest.fixture
def _clean_env(monkeypatch):
    """Strip DATABASE_* knobs so a developer's shell can't perturb construction, and
    make an unreachable engine fail fast instead of looping ~60s before os._exit."""
    for var in (
        "DATABASE_URI",
        "DATABASE_URI_READONLY",
        "IGNORE_REGEX_CHECK",
        "DATABASE_POOL_SIZE",
        "DATABASE_POOL_MAX_OVERFLOW",
        "DATABASE_POOL_TIMEOUT",
        "DATABASE_POOL_RECYCLE",
        "DATABASE_POOL_PRE_PING",
        "DATABASE_POOL_RESET_ON_RETURN",
        "DATABASE_REQUEST_RETRY_ATTEMPTS",
        "DATABASE_REQUEST_RETRY_DELAY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DATABASE_RETRY_TIMEOUT", "0")


# --- the DB fixture ---------------------------------------------------------------
@pytest.fixture
def db(db_engine, tmp_path, quiet_logger, _clean_env):
    """A ready ``Database`` bound to ``db_engine`` with a freshly reset schema.

    Isolation is schema-level (DB methods commit internally, so transaction rollback
    is impossible): SQLite gets a brand-new temp file per test; PostgreSQL/MariaDB get
    a drop_all + create_all on the shared test database before each test.
    """
    uri = resolve_uri(db_engine, tmp_path)
    reset_schema(uri)

    from Database import Database  # noqa: E402 — imported after sys.path injection

    database = Database(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database
    finally:
        database.close()
