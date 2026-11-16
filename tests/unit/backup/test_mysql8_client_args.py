"""MySQL client flags follow the client family and version, for either server engine."""

import sys
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src/common/core/backup"))
import backup  # noqa: E402


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
    monkeypatch.setattr(backup, "inspect", lambda _: inspector, raising=False)
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
    monkeypatch.setattr(backup, "check_output", lambda *args, **kwargs: version, raising=False)
    monkeypatch.setattr(backup, "Base", SimpleNamespace(metadata=SimpleNamespace(drop_all=lambda _: None)))
    monkeypatch.setattr(backup, "MetaData", lambda: SimpleNamespace(reflect=lambda **kwargs: None, drop_all=lambda **kwargs: None))
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
