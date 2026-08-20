"""Shared pytest configuration and fixtures for the BunkerWeb unit-test suite.

Responsibilities:
  * inject the ``src/common/db`` (+utils/api) directories onto ``sys.path`` before
    any test imports ``Database``/``model`` (bare-import layout);
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

_REPO_ROOT = _HERE.parents[1]
for _path in reversed(
    (
        _REPO_ROOT / "src" / "common" / "db",
        _REPO_ROOT / "src" / "common" / "utils",
        _REPO_ROOT / "src" / "common" / "api",
    )
):
    _path_str = str(_path)
    if _path_str in sys.path:
        sys.path.remove(_path_str)
    sys.path.insert(0, _path_str)

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


# --- the api_app lane is opt-in and EXCLUSIVE, and must stay that way -------------
# `api_app/` imports the API's `app` package. `ui/conftest.py` relies on `import app` resolving
# uniquely to `src/ui/app`, so the two cannot share an interpreter.
#
# What the collision actually looks like, measured rather than assumed: the loser raises
# `ModuleNotFoundError` on its first import -- `app.auth` missing when the UI won,
# `app.models.ui_database` missing when api_app won -- because the two packages have disjoint
# submodules. It is loud in both directions, and it happens at *collection* time, so it does not
# fail one test, it interrupts the whole run. (An earlier version of this comment said the wrong
# module was picked up silently. It is not, and the difference matters: someone who measures it,
# finds an error rather than the described silence, and concludes the warning was alarmist is
# exactly who relaxes this guard.)
#
# Two things about the ignore itself, both measured, because the obvious spelling does neither:
#
#   * `"api_app"` ignores the DIRECTORY node, which is what stops a tree walk descending into it
#     and loading `api_app/conftest.py`. Without it that conftest runs on every ordinary
#     `pytest tests/unit`, inserting `src/api` at `sys.path[0]`; the suite then survives only
#     because `ui/conftest.py` sorts later and re-inserts `src/ui` before anything imports `app`.
#     Alphabetical luck is not a guard.
#   * `"api_app/*"` ignores the test FILES, which is what still applies when the directory is
#     named directly on the command line -- the directory pattern is not consulted for a path the
#     user asked for by name. Without it, `pytest tests/unit/api_app` runs the lane with no flag.
#
# Both spellings are needed; each one alone leaves one of those two doors open.
#
# Exclusive, not merely opt-in: with the flag unset the lane is ignored, with it set everything
# *else* is. An additive flag -- ignoring nothing when set -- meant `BW_API_APP_LANE=1 pytest
# tests/unit` collected 0 of ~4100 tests and reported one error naming `app.models.ui_database`,
# i.e. pointing at the UI rather than at the lane that caused it. A CI job that exports the flag
# once in its environment gets a silent coverage hole that way.
#
# The dotfile/underscore filter is load-bearing, not tidiness: `.venv-unit/` lives inside
# `tests/unit/`, so a bare `iterdir()` would emit an ignore for the virtualenv.
collect_ignore_glob = (
    [
        _pattern
        for _child in _HERE.iterdir()
        if _child.is_dir() and not _child.name.startswith((".", "_")) and _child.name != "api_app"
        for _pattern in (_child.name, f"{_child.name}/*")
    ]
    if os.getenv("BW_API_APP_LANE") == "1"
    else ["api_app", "api_app/*"]
)
