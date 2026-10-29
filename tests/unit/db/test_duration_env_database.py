"""The DATABASE_* time settings accept the 1.6.16 suffixes (dev 3075b9d16).

Read at construction: ``DATABASE_POOL_TIMEOUT`` and ``DATABASE_POOL_RECYCLE`` feed the engine,
``DATABASE_REQUEST_RETRY_DELAY`` the retry loop. ``DATABASE_RETRY_TIMEOUT`` only matters while the
database is unreachable, so it is checked on the shipped source.
"""

import logging
from pathlib import Path

import pytest

from Database import Database

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ("DATABASE_POOL_TIMEOUT", "DATABASE_POOL_RECYCLE", "DATABASE_REQUEST_RETRY_DELAY", "DATABASE_RETRY_TIMEOUT")


def _database(tmp_path, monkeypatch, **env):
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Database(logging.getLogger("duration-env"), sqlalchemy_string=f"sqlite:///{tmp_path / 'db.sqlite3'}")


@pytest.mark.parametrize(("value", "expected"), [("5", 5), ("5s", 5), ("1m", 60), ("500ms", 0.5), ("0", 0)])
def test_pool_timeout(tmp_path, monkeypatch, value, expected):
    assert _database(tmp_path, monkeypatch, DATABASE_POOL_TIMEOUT=value)._engine_kwargs["pool_timeout"] == expected


@pytest.mark.parametrize(("value", "expected"), [("1800", 1800), ("30m", 1800), ("1h", 3600), ("-1", -1)])
def test_pool_recycle(tmp_path, monkeypatch, value, expected):
    assert _database(tmp_path, monkeypatch, DATABASE_POOL_RECYCLE=value)._engine_kwargs["pool_recycle"] == expected


@pytest.mark.parametrize(("value", "expected"), [("0.25", 0.25), ("250ms", 0.25), ("1s", 1.0), ("2", 2.0)])
def test_request_retry_delay(tmp_path, monkeypatch, value, expected):
    assert _database(tmp_path, monkeypatch, DATABASE_REQUEST_RETRY_DELAY=value)._request_retry_delay == expected


@pytest.mark.parametrize("name", ["DATABASE_POOL_TIMEOUT", "DATABASE_POOL_RECYCLE"])
def test_an_unparsable_value_falls_back_to_the_default(tmp_path, monkeypatch, name):
    default = _database(tmp_path, monkeypatch)._engine_kwargs
    broken = _database(tmp_path, monkeypatch, **{name: "soon"})._engine_kwargs
    assert broken == default


def test_retry_timeout_goes_through_the_parser():
    source = (ROOT / "src" / "common" / "db" / "Database.py").read_text()
    assert 'parse_duration(DATABASE_RETRY_TIMEOUT, "s")' in source
    assert "DATABASE_RETRY_TIMEOUT.isdigit()" not in source
