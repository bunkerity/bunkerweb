"""Per-engine URI construction, reachability probing and schema reset.

Backs the multi-engine ``db`` fixture in ``conftest.py``. SQLite uses a temp file
(pure ``sqlite://`` / ``:memory:`` is rejected by ``Database.DB_STRING_RX`` and would
also break under the pool); PostgreSQL/MariaDB URIs come from env vars and point at the
throwaway containers in ``misc/dev/docker-compose.test-db.yml``.
"""

import socket

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

# Env var holding each non-sqlite engine's connection URI.
ENGINE_ENV = {
    "postgresql": "BW_TEST_PG_URI",
    "mariadb": "BW_TEST_MARIA_URI",
}

_DEFAULT_PORT = {"postgresql": 5432, "mariadb": 3306, "mysql": 3306}
# Drivers BunkerWeb's Database injects — mirror them so our raw DDL engine matches.
_DRIVERS = {"postgresql": "psycopg", "mysql": "pymysql", "mariadb": "pymysql"}


def build_sqlite_uri(tmp_path) -> str:
    """Return a ``sqlite:////abs/path`` URI for a fresh, empty temp file."""
    db_file = tmp_path / "unit.sqlite3"
    db_file.touch()
    # db_file is absolute (leading '/'), so "sqlite:///" + "/abs" => canonical 4-slash form.
    return f"sqlite:///{db_file}"


def env_uri(engine, env):
    """Return the configured URI for a non-sqlite engine, or ``None`` if unset."""
    return env.get(ENGINE_ENV[engine])


def _with_driver(uri):
    """Inject the recommended DBAPI driver (psycopg/pymysql) if none was specified."""
    url = make_url(uri)
    backend = url.get_backend_name()
    if "+" not in url.drivername and backend in _DRIVERS:
        url = url.set(drivername=f"{backend}+{_DRIVERS[backend]}")
    return url


def is_reachable(uri, timeout: float = 1.0) -> bool:
    """Cheap TCP probe so an unreachable engine becomes a clean skip rather than an
    uncatchable ``os._exit(1)`` inside the Database constructor."""
    url = make_url(uri)
    if url.get_backend_name() == "sqlite":
        return True
    host = url.host or "127.0.0.1"
    port = url.port or _DEFAULT_PORT.get(url.get_backend_name(), 0)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def reset_schema(uri) -> None:
    """Drop and recreate every table on a throwaway ``NullPool`` engine.

    This is the per-test isolation primitive. ``Base.metadata`` handles dialect
    specifics (ENUM types, identity columns, FK order) for free, so it doubles as a
    per-engine DDL smoke test.
    """
    from model import Base  # imported lazily, after conftest injected sys.path

    engine = create_engine(_with_driver(uri), poolclass=NullPool)
    try:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
