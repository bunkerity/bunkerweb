"""DATABASE_CONNECT_TIMEOUT and DATABASE_READ_TIMEOUT reach each driver's connect arguments (dev 62056020f).

A network database whose peer vanishes without a reset used to block the scheduler, UI or API forever:
the engine was built with pool settings only. The engine is built against SQLite here (no server needed)
and ``create_engine`` is intercepted to read the ``connect_args`` each backend would receive.
"""

import json
import logging
from pathlib import Path

import pytest

import Database as database_module
from Database import Database

ROOT = Path(__file__).resolve().parents[3]
NAMES = ("DATABASE_CONNECT_TIMEOUT", "DATABASE_READ_TIMEOUT")

MARIADB = "mariadb+pymysql://u:p@db:3306/bw"
MYSQL = "mysql+pymysql://u:p@db:3306/bw"
POSTGRES = "postgresql+psycopg://u:p@db:5432/bw"


def _database(tmp_path, monkeypatch, **env):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Database(logging.getLogger("driver-timeouts"), sqlalchemy_string=f"sqlite:///{tmp_path / 'db.sqlite3'}")


def _connect_args(db, uri, monkeypatch, **kwargs):
    seen = {}

    def fake_create_engine(url, **options):
        seen["options"] = options
        return object()

    monkeypatch.setattr(database_module, "create_engine", fake_create_engine)
    db._create_engine(uri, **kwargs)
    return seen["options"].get("connect_args", {})


@pytest.mark.parametrize("uri", [MARIADB, MYSQL])
def test_mysql_family_gets_connect_read_and_write_timeouts(tmp_path, monkeypatch, uri):
    args = _connect_args(_database(tmp_path, monkeypatch), uri, monkeypatch)
    assert args == {"connect_timeout": 10, "read_timeout": 300, "write_timeout": 300}


def test_postgresql_gets_the_connect_timeout_and_keepalives_but_no_query_deadline(tmp_path, monkeypatch):
    args = _connect_args(_database(tmp_path, monkeypatch), POSTGRES, monkeypatch)
    assert args["connect_timeout"] == 10
    assert args["keepalives"] == 1
    assert "read_timeout" not in args and "options" not in args


def test_sqlite_gets_nothing(tmp_path, monkeypatch):
    db = _database(tmp_path, monkeypatch)
    assert _connect_args(db, f"sqlite:///{tmp_path / 'other.sqlite3'}", monkeypatch) == {}


@pytest.mark.parametrize(("value", "seconds"), [("3", 3), ("3s", 3), ("2m", 120), ("1500ms", 2)])
def test_the_settings_accept_time_suffixes(tmp_path, monkeypatch, value, seconds):
    db = _database(tmp_path, monkeypatch, DATABASE_CONNECT_TIMEOUT=value, DATABASE_READ_TIMEOUT=value)
    args = _connect_args(db, MARIADB, monkeypatch)
    assert (args["connect_timeout"], args["read_timeout"]) == (seconds, seconds)


def test_a_zero_read_timeout_disables_it_and_a_zero_connect_timeout_falls_back(tmp_path, monkeypatch):
    db = _database(tmp_path, monkeypatch, DATABASE_CONNECT_TIMEOUT="0", DATABASE_READ_TIMEOUT="0")
    # The drivers reject 0 and wait forever when no value is set, so 0 means "leave it out".
    assert _connect_args(db, MARIADB, monkeypatch) == {"connect_timeout": 10}


@pytest.mark.parametrize("name", NAMES)
def test_an_unparsable_value_falls_back_to_the_default(tmp_path, monkeypatch, name):
    default_db = _database(tmp_path, monkeypatch)
    broken_db = _database(tmp_path, monkeypatch, **{name: "soon"})  # built before create_engine is intercepted
    assert _connect_args(broken_db, MARIADB, monkeypatch) == _connect_args(default_db, MARIADB, monkeypatch)


def test_a_timeout_in_the_uri_query_string_wins(tmp_path, monkeypatch):
    db = _database(tmp_path, monkeypatch)
    args = _connect_args(db, MARIADB + "?connect_timeout=42", monkeypatch)
    assert "connect_timeout" not in args and args["read_timeout"] == 300


def test_a_caller_connect_args_override_the_defaults(tmp_path, monkeypatch):
    db = _database(tmp_path, monkeypatch)
    args = _connect_args(db, MARIADB, monkeypatch, connect_args={"connect_timeout": 1})
    assert args["connect_timeout"] == 1 and args["read_timeout"] == 300


def test_every_engine_site_goes_through_the_helper():
    source = (ROOT / "src" / "common" / "db" / "Database.py").read_text()
    assert source.count("create_engine(") == source.count("self._create_engine(") + 2  # the def line and the helper's own call


def test_the_plugin_declares_both_settings():
    settings = json.loads((ROOT / "src" / "common" / "core" / "db" / "plugin.json").read_text())["settings"]
    assert settings["DATABASE_CONNECT_TIMEOUT"]["default"] == "10s"
    assert settings["DATABASE_READ_TIMEOUT"]["default"] == "5m"
    for lang in ("", ".de", ".es", ".fr", ".zh"):
        readme = (ROOT / "src" / "common" / "core" / "db" / f"README{lang}.md").read_text()
        assert "DATABASE_CONNECT_TIMEOUT" in readme and "DATABASE_READ_TIMEOUT" in readme, lang
