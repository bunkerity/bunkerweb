"""Which client binary a MariaDB/MySQL backup runs, and which TLS flags it passes.

Both images ship `mariadb-client`, and Debian still provides `/usr/bin/mysql -> mariadb`, so the
old hardcoded `mysql` was already executing the MariaDB client through a symlink. That matters:
MariaDB clients verify opportunistic TLS by default, and the server's generated certificate is
self-signed, so a dump against it fails on verification with nothing in the command line that
explains why. `ssl=false` in DATABASE_URI was ignored outright.
"""

import sys
from pathlib import Path

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402
from backup import mysql_client_command, mysql_connection_args  # noqa: E402

# Named so a floor can assert they are still populated: an emptied parametrize list does not
# fail, it collects nothing, and the run still reports "N passed" (RULE 13).
MARIADB_NAMES = [("dump", "mariadb-dump"), ("restore", "mariadb")]
MYSQL_NAMES = [("dump", "mysqldump"), ("restore", "mysql")]


def test_the_client_name_tables_are_populated():
    """Floor, not an exact count -- growth here is collaboration: a new operation gets a row."""
    assert len(MARIADB_NAMES) >= 2, "MARIADB_NAMES emptied: the client-selection tests collect nothing"
    assert len(MYSQL_NAMES) >= 2, "MYSQL_NAMES emptied: the fallback tests collect nothing"


class TestClientSelection:
    @pytest.mark.parametrize(("operation", "expected"), MARIADB_NAMES)
    def test_the_mariadb_client_is_preferred_when_present(self, operation, expected, monkeypatch):
        monkeypatch.setattr(backup, "which", lambda name: f"/usr/bin/{name}")
        assert mysql_client_command(operation) == (expected, True)

    @pytest.mark.parametrize(("operation", "expected"), MYSQL_NAMES)
    def test_it_falls_back_to_the_mysql_names(self, operation, expected, monkeypatch):
        monkeypatch.setattr(backup, "which", lambda name: None)
        assert mysql_client_command(operation) == (expected, False)


class TestConnectionArgs:
    def test_ssl_true_asks_for_tls(self):
        assert mysql_connection_args({"ssl": "true"}, False) == ["--ssl"]

    def test_ssl_false_is_honoured_rather_than_ignored(self):
        """The loop this replaced only ever looked for `"true"`, so `ssl=false` in DATABASE_URI
        silently did nothing at all."""
        assert mysql_connection_args({"ssl": "false"}, True) == ["--skip-ssl"]

    def test_a_mariadb_client_skips_verification_when_ssl_is_unset(self):
        assert mysql_connection_args({}, True) == ["--skip-ssl-verify-server-cert"]

    def test_a_mysql_client_gets_no_tls_flag_when_ssl_is_unset(self):
        assert mysql_connection_args({}, False) == []

    def test_an_explicit_ssl_setting_beats_the_mariadb_default(self):
        assert mysql_connection_args({"ssl": "true"}, True) == ["--ssl"]

    def test_the_charset_is_passed_through(self):
        assert mysql_connection_args({"charset": "utf8mb4"}, False) == ["--default-character-set", "utf8mb4"]

    def test_a_repeated_query_key_takes_the_last_value_not_the_tuple(self):
        """SQLAlchemy hands back a tuple when a key appears twice in the URI. Formatting the tuple
        into argv produces a flag like `--default-character-set ('utf8', 'utf8mb4')`, which the
        client rejects."""
        args = mysql_connection_args({"charset": ("utf8", "utf8mb4"), "ssl": ("false", "true")}, True)
        assert args == ["--ssl", "--default-character-set", "utf8mb4"]

    def test_a_non_string_ssl_value_does_not_raise(self):
        assert mysql_connection_args({"ssl": True}, False) == ["--ssl"]
