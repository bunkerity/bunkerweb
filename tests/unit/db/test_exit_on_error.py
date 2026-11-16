"""``Database(exit_on_error=False)`` raises DatabaseInitError instead of exiting the process (dev 4a91e1e13, used by ``bwcli support``).

``bwcli support`` is run most often when something is broken, so it builds the Database to raise and still writes a bundle
from what it can read. The default stays an exit: the scheduler, UI and API rely on it.
"""

import logging

import pytest

import Database as database_module
from Database import Database, DatabaseInitError

LOGGER = logging.getLogger("exit-on-error")


def test_an_invalid_uri_raises_instead_of_exiting():
    with pytest.raises(DatabaseInitError, match="Invalid database string"):
        Database(LOGGER, sqlalchemy_string="notadb://user:hunter2hunter2@host/db", exit_on_error=False)


def test_the_default_still_exits_the_process(monkeypatch):
    def fake_exit(code):
        raise SystemExit(code)

    monkeypatch.setattr(database_module, "_exit", fake_exit)
    with pytest.raises(SystemExit):
        Database(LOGGER, sqlalchemy_string="notadb://user:hunter2hunter2@host/db")


def test_an_unreachable_server_raises_at_once_without_the_password(monkeypatch):
    monkeypatch.setenv("DATABASE_RETRY_TIMEOUT", "300")  # exit_on_error=False must not wait for it
    with pytest.raises(DatabaseInitError) as error:
        Database(LOGGER, sqlalchemy_string="postgresql://bunkerweb:hunter2hunter2@127.0.0.1:1/bw", exit_on_error=False)
    assert "hunter2hunter2" not in str(error.value)
