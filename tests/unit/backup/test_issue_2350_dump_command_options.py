"""The database dump commands carry the options a large database needs.

A backup of a big MariaDB/MySQL database failed because the dump ran with the client defaults: a
table lock for the whole run, every row buffered in memory, and a packet size too small for a large
row. PostgreSQL dumps had no ownership/privilege stripping, so a restore on another role failed. The
dump also crashed when a failing client reported no stderr at all. Refs #2350.
"""

import sys
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402

NOW = datetime.now().astimezone()
OK = CompletedProcess([], 0, b"-- dump", b"")


def dump_command(uri, tmp_path, procs=(OK,)):
    db = SimpleNamespace(database_uri=uri, sql_engine=MagicMock())
    with patch.object(backup, "inspect", create=True) as inspect_mock, patch.object(backup, "run", side_effect=list(procs)) as run_mock:
        inspect_mock.return_value.get_table_names.return_value = ["bw_plugins"]
        inspect_mock.return_value.get_view_names.return_value = []
        backup.backup_database(NOW, db=db, backup_dir=tmp_path)
    return run_mock.call_args.args[0]


@pytest.mark.parametrize("engine", ["mariadb+pymysql", "mysql+pymysql"])
def test_mysql_family_dump_streams_rows_without_locking_and_raises_the_packet_size(engine, tmp_path):
    cmd = dump_command(f"{engine}://bw:s@db:3306/bunkerweb", tmp_path)

    for option in (
        "--single-transaction",  # consistent snapshot instead of a table lock
        "--quick",  # rows are streamed, not buffered in client memory
        "--lock-tables=false",
        "--skip-add-locks",
        "--max_allowed_packet=2147483648",  # a large row must fit in one packet
        "--default-character-set=utf8mb4",
        "--triggers",
    ):
        assert option in cmd, f"{option} missing from {cmd}"


def test_postgresql_dump_is_portable_across_roles_and_never_prompts(tmp_path):
    cmd = dump_command("postgresql+psycopg://bw:s@db:5432/bunkerweb", tmp_path)

    for option in ("--no-password", "--no-owner", "--no-privileges", "--format=plain"):
        assert option in cmd, f"{option} missing from {cmd}"


def test_a_failing_dump_that_reports_no_stderr_exits_cleanly(tmp_path):
    """The client can die without writing to stderr; decoding `None` used to raise instead of reporting the failure."""
    silent_failure = CompletedProcess([], 1, b"", None)

    with pytest.raises(SystemExit) as raised:
        dump_command("mariadb+pymysql://bw:s@db:3306/bunkerweb", tmp_path, procs=[silent_failure])

    assert raised.value.code == 1
