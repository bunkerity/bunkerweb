"""The database lock between real processes, and the three scripts that take it.

`backup.acquire_db_lock` guards the backup job, `bwcli plugin backup save` and `restore` against
each other. Two threads of one process cannot show that, so these tests start processes: they
contend for the lock, and a holder that dies with `SIGKILL` must not leave a lock behind.
"""

import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from runpy import run_path
from time import sleep, time
from types import ModuleType

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402

from common_utils import DatabaseLockBusy  # noqa: E402

PRELUDE = """
import sys
sys.path[:0] = {paths!r}
import backup
from pathlib import Path
backup.DB_LOCK_FILE = Path({lock!r})
release = getattr(backup, "release_db_lock", None) or (lambda handle: backup.DB_LOCK_FILE.unlink(missing_ok=True))
"""


def _python(tmp_path, lock, body):
    script = tmp_path / f"script-{abs(hash(body))}.py"
    script.write_text(PRELUDE.format(paths=sys.path, lock=str(lock)) + textwrap.dedent(body))
    return script


@pytest.fixture
def lock(tmp_path):
    return tmp_path / "db.lock"


def test_only_one_of_several_processes_runs_at_a_time(tmp_path, lock):
    journal = tmp_path / "journal"
    go = time() + 3
    script = _python(
        tmp_path,
        lock,
        f"""
        from time import sleep, time
        while time() < {go}:
            sleep(0.005)
        handle = backup.acquire_db_lock()
        with open({str(journal)!r}, "a") as out:
            out.write("start\\n")
        sleep(0.3)
        with open({str(journal)!r}, "a") as out:
            out.write("end\\n")
        release(handle)
        """,
    )

    processes = [subprocess.Popen([sys.executable, str(script)]) for _ in range(5)]
    assert [process.wait(timeout=60) for process in processes] == [0] * 5

    assert journal.read_text().split() == ["start", "end"] * 5


def test_a_holder_killed_with_sigkill_leaves_no_lock_behind(tmp_path, lock, monkeypatch):
    ready = tmp_path / "ready"
    script = _python(
        tmp_path,
        lock,
        f"""
        from pathlib import Path
        from time import sleep
        backup.acquire_db_lock()
        Path({str(ready)!r}).write_text("x")
        sleep(60)
        """,
    )
    holder = subprocess.Popen([sys.executable, str(script)])
    try:
        deadline = time() + 30
        while not ready.exists():
            assert time() < deadline and holder.poll() is None, "the holder never took the lock"
            sleep(0.05)
        holder.send_signal(signal.SIGKILL)
        holder.wait(timeout=10)
    finally:
        holder.kill()

    monkeypatch.setattr(backup, "DB_LOCK_FILE", lock)
    started = time()
    handle = backup.acquire_db_lock()

    assert time() - started < 5
    backup.release_db_lock(handle)


def test_a_live_process_keeps_the_lock_against_this_one(tmp_path, lock, monkeypatch):
    ready = tmp_path / "ready"
    script = _python(
        tmp_path,
        lock,
        f"""
        from pathlib import Path
        from time import sleep
        backup.acquire_db_lock()
        Path({str(ready)!r}).write_text("x")
        sleep(60)
        """,
    )
    holder = subprocess.Popen([sys.executable, str(script)])
    try:
        deadline = time() + 30
        while not ready.exists():
            assert time() < deadline and holder.poll() is None, "the holder never took the lock"
            sleep(0.05)
        monkeypatch.setattr(backup, "DB_LOCK_FILE", lock)
        with pytest.raises(DatabaseLockBusy, match=str(holder.pid)):
            backup.acquire_db_lock(timeout=1.5)
    finally:
        holder.kill()
        holder.wait(timeout=10)


# -- the three scripts -------------------------------------------------------------------------

SCRIPTS = {
    "save": _BACKUP / "bwcli" / "save.py",
    "restore": _BACKUP / "bwcli" / "restore.py",
    "backup-data": _BACKUP / "jobs" / "backup-data.py",
}


class _FakeBackup(ModuleType):
    """Everything the three scripts import from `backup`, old and new, recording how it is used."""

    def __init__(self, tmp_path, busy):
        super().__init__("backup")
        self.busy = busy
        self.released = []
        self.DatabaseLockBusy = DatabaseLockBusy
        self.DB_LOCK_FILE = tmp_path / "db.lock"
        self.DB_LOCK_FILE.write_text("someone else's marker")
        self.BACKUP_DIR = tmp_path / "backups"
        self.LOGGER = __import__("logging").getLogger("fake-backup")
        self.ensure_backup_dir = lambda directory: Path(directory)
        self.backup_database = lambda *args, **kwargs: (object(), None)
        self.update_cache_file = lambda *args, **kwargs: None
        self.restore_database = lambda *args, **kwargs: None
        self.sorted_backups = lambda *args, **kwargs: []
        self.rotate_backups = lambda *args, **kwargs: None

    def acquire_db_lock(self, *args, **kwargs):
        if self.busy:
            raise DatabaseLockBusy("database is locked, try again later")
        return 41

    def release_db_lock(self, handle):
        self.released.append(handle)


def _run(name, fake, monkeypatch, argv):
    monkeypatch.setitem(sys.modules, "backup", fake)
    monkeypatch.setattr(sys, "argv", [name, *argv])
    with pytest.raises(SystemExit) as exit_info:
        run_path(str(SCRIPTS[name]), run_name="__main__")
    return exit_info.value.code


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_a_busy_lock_ends_the_script_with_status_2_and_removes_nothing(name, tmp_path, monkeypatch):
    fake = _FakeBackup(tmp_path, busy=True)

    assert _run(name, fake, monkeypatch, []) == 2

    assert fake.released == []
    assert fake.DB_LOCK_FILE.read_text() == "someone else's marker", "the script removed a lock it never held"


def test_save_releases_the_handle_it_was_given(tmp_path, monkeypatch):
    fake = _FakeBackup(tmp_path, busy=False)

    assert _run("save", fake, monkeypatch, ["-d", str(tmp_path / "out")]) == 0

    assert fake.released == [41]
    assert fake.DB_LOCK_FILE.is_file(), "the lock file must stay: it is the lock"


def test_restore_releases_the_handle_it_was_given(tmp_path, monkeypatch):
    fake = _FakeBackup(tmp_path, busy=False)
    archive = tmp_path / "backup.zip"
    archive.write_bytes(b"")
    monkeypatch.setenv("BWCLI_RESTORE_SAFETY_DIRECTORY", str(tmp_path / "safety"))

    assert _run("restore", fake, monkeypatch, [str(archive)]) == 0

    assert fake.released == [41]
    assert fake.DB_LOCK_FILE.is_file()


def test_the_backup_job_releases_the_handle_it_was_given(tmp_path, monkeypatch):
    fake = _FakeBackup(tmp_path, busy=False)
    monkeypatch.setenv("USE_BACKUP", "no")
    monkeypatch.delenv("FORCE_BACKUP", raising=False)

    assert _run("backup-data", fake, monkeypatch, []) == 0

    assert fake.released == [41]
    assert fake.DB_LOCK_FILE.is_file()


def test_an_exception_after_the_lock_still_releases_it(tmp_path, monkeypatch):
    fake = _FakeBackup(tmp_path, busy=False)
    fake.backup_database = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("dump failed"))

    assert _run("save", fake, monkeypatch, ["-d", str(tmp_path / "out")]) == 1

    assert fake.released == [41]
