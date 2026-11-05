"""Which client binary a MariaDB/MySQL backup runs, and which TLS flags it passes.

Both images ship `mariadb-client`, and Debian still provides `/usr/bin/mysql -> mariadb`, so the
old hardcoded `mysql` was already executing the MariaDB client through a symlink. That matters:
MariaDB clients verify opportunistic TLS by default, and the server's generated certificate is
self-signed, so a dump against it fails on verification with nothing in the command line that
explains why. `ssl=false` in DATABASE_URI was ignored outright.
"""

import sys
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import MagicMock
from zipfile import ZipFile

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


@pytest.mark.parametrize("engine", ["mysql", "mariadb"])
@pytest.mark.parametrize("ssl", [None, "true", "false"])
@pytest.mark.parametrize(
    ("binary", "version", "column_statistics", "mariadb_client"),
    [
        ("mysqldump", "mysqldump  Ver 8.4.10 for Linux on x86_64 (MySQL Community Server - GPL)", True, False),
        ("mysqldump", "mysqldump  Ver 8.0.45 for Linux on x86_64 (MySQL Community Server - GPL)", True, False),
        ("mysqldump", "mysqldump  Ver 9.5.0 for Linux on x86_64 (MySQL Community Server - GPL)", True, False),
        ("mysqldump", "mysqldump  Ver 10.13 Distrib 5.7.44, for Linux (x86_64)", False, False),
        ("mariadb-dump", "mariadb-dump  Ver 10.19 Distrib 11.8.8-MariaDB, for Linux (x86_64)", False, True),
        ("mysqldump", "mysqldump  Ver 10.19 Distrib 10.5.29-MariaDB, for Linux (x86_64)", False, True),
    ],
)
def test_dump_options_follow_client_version_not_binary_or_server_name(engine, ssl, binary, version, column_statistics, mariadb_client, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "which", lambda name: f"/usr/bin/{name}" if name == binary else None)
    monkeypatch.setattr(backup, "check_output", lambda *args, **kwargs: version, raising=False)
    inspector = SimpleNamespace(get_table_names=lambda: ["items"], get_view_names=lambda: [])
    monkeypatch.setattr(backup, "inspect", lambda _: inspector)
    commands = []

    def dump(cmd, **kwargs):
        commands.append(cmd)
        return CompletedProcess(cmd, 0, b"-- dump\n", b"")

    monkeypatch.setattr(backup, "run", dump)
    query = f"?ssl={ssl}" if ssl is not None else ""
    db = SimpleNamespace(database_uri=f"{engine}+pymysql://bw:s@db:3306/bunkerweb{query}", sql_engine=MagicMock())
    _, archive = backup.backup_database(datetime.now().astimezone(), db=db, backup_dir=tmp_path)

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd[0] == binary
    assert ("--column-statistics=0" in cmd) == column_statistics
    assert ("--set-gtid-purged=OFF" in cmd) == column_statistics
    assert ("--skip-ssl-verify-server-cert" in cmd) == (mariadb_client and ssl is None)
    if ssl is not None:
        expected = ("--ssl-mode=REQUIRED" if ssl == "true" else "--ssl-mode=DISABLED") if column_statistics else ("--ssl" if ssl == "true" else "--skip-ssl")
        assert expected in cmd
        if column_statistics:
            assert "--ssl" not in cmd and "--skip-ssl" not in cmd
    with ZipFile(archive) as zipf:
        assert zipf.read(archive.with_suffix(".sql").name) == b"-- dump\n"


@pytest.mark.parametrize("engine", ["mysql", "mariadb"])
@pytest.mark.parametrize("ssl", [None, "true", "false"])
@pytest.mark.parametrize(
    ("binary", "version", "mysql8_client", "mariadb_client"),
    [
        ("mysql", "mysql  Ver 8.4.10 for Linux on x86_64 (Source distribution)", True, False),
        ("mysql", "mysql  Ver 8.0.45 for Linux on x86_64 (MySQL Community Server - GPL)", True, False),
        ("mysql", "mysql  Ver 9.5.0 for Linux on x86_64 (MySQL Community Server - GPL)", True, False),
        ("mysql", "mysql  Ver 14.14 Distrib 5.7.44, for Linux (x86_64)", False, False),
        ("mariadb", "mariadb  Ver 15.2 Distrib 11.8.8-MariaDB, for Linux (x86_64)", False, True),
        ("mysql", "mysql  Ver 15.1 Distrib 10.5.29-MariaDB, for Linux (x86_64)", False, True),
    ],
)
def test_restore_tls_options_follow_client_version(engine, ssl, binary, version, mysql8_client, mariadb_client, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "which", lambda name: f"/usr/bin/{name}" if name == binary else None)
    monkeypatch.setattr(backup, "check_output", lambda *args, **kwargs: version)
    monkeypatch.setattr(backup, "Base", SimpleNamespace(metadata=SimpleNamespace(drop_all=lambda _: None)))
    commands = []
    sql = b"CREATE TABLE items (id INT);\n"

    def restore(cmd, **kwargs):
        commands.append(cmd)
        assert kwargs["input"] == sql
        return CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(backup, "run", restore)
    archive = tmp_path / f"backup-{engine}-2026-11-05_00-00-00.zip"
    with ZipFile(archive, "w") as zipf:
        zipf.writestr(archive.with_suffix(".sql").name, sql)
    query = f"?ssl={ssl}" if ssl is not None else ""
    db = SimpleNamespace(database_uri=f"{engine}+pymysql://bw:s@db:3306/bunkerweb{query}", sql_engine=MagicMock(), checked_changes=lambda **kwargs: "")
    assert backup.restore_database(archive, db=db) is db

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd[0] == binary
    assert ("--skip-ssl-verify-server-cert" in cmd) == (mariadb_client and ssl is None)
    if ssl is not None:
        expected = ("--ssl-mode=REQUIRED" if ssl == "true" else "--ssl-mode=DISABLED") if mysql8_client else ("--ssl" if ssl == "true" else "--skip-ssl")
        assert expected in cmd
    if mysql8_client:
        assert "--ssl" not in cmd and "--skip-ssl" not in cmd
