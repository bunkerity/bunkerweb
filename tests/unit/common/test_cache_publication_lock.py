"""A cache write must not land inside a `/cache` push, or the push deletes it.

`POST /cache` publishes by REPLACING every top-level entry of the destination with the archive's
copy (`api.lua`'s /confs handler -> `pushswap.swap`: park the live entry into `.bw-trash`, rename
the staged one into its place, `rm -rf` the trash). On the Linux package and all-in-one that
destination is the same directory the worker's jobs write into, so a file written after the tar was
built and before the swap completes is destroyed -- while its database row, written in the same
call, says it is current.

Seen live, Linux CI run `7c7c50e66` job 103950399340:

    11:10:51 [CUSTOM-CERT] Detected change in default-server's certificate   <- cache_file() wrote
    11:10:51 [API.CALLER]  Successfully sent API request to .../cache        <- swap rolled it back
    11:10:53 [CUSTOMCERT]  error while reading files : /var/cache/bunkerweb/customcert/
                           default-server/cert.pem ... No such file or directory
    11:10:54 (same again -- and `custom-cert` is `every: day`)

The instance served the internal self-signed certificate instead of the operator's, with the job
recorded a success.
"""

from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock
from os import O_CREAT, O_RDWR, close as os_close, open as os_open
from pathlib import Path
from re import search
from threading import Thread
from unittest.mock import Mock

import pytest

import jobs
from jobs import CACHE_PUBLICATION_LOCK_NAME, CACHE_PUBLICATION_LOCK_WAIT, Job, cache_publication_lock


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    """Point the publication lock at a temporary tree instead of /var/cache/bunkerweb."""
    monkeypatch.setattr(jobs, "CACHE_PATH", tmp_path)
    return tmp_path


@pytest.fixture
def job(cache_root):
    """A Job built without ``__init__`` -- that one hardcodes /var/cache/bunkerweb/<plugin>."""
    instance = Job.__new__(Job)
    instance.job_path = cache_root / "customcert"
    instance.job_path.mkdir(parents=True, exist_ok=True)
    instance.job_name = "custom-cert"
    instance.logger = Mock()
    instance.db = Mock()
    instance.db.upsert_job_cache.return_value = ""
    instance.db.delete_job_cache.return_value = ""
    instance.db.get_jobs_cache_files.return_value = []
    return instance


def _probe(cache_root) -> bool:
    """Would a second process' exclusive flock be refused right now?

    A separate file descriptor, deliberately: `flock(2)` treats descriptors from separate `open`
    calls independently even inside one process, so this answers the same question a concurrent
    worker child asks.
    """
    fd = os_open((cache_root / CACHE_PUBLICATION_LOCK_NAME).as_posix(), O_CREAT | O_RDWR, 0o660)
    try:
        try:
            flock(fd, LOCK_EX | LOCK_NB)
        except OSError:
            return True
        flock(fd, LOCK_UN)
        return False
    finally:
        os_close(fd)


def test_cache_file_holds_the_publication_lock_while_it_writes(job, cache_root):
    """The regression this file exists for: the write and its row inside the lock."""
    seen = []
    job.db.upsert_job_cache.side_effect = lambda *a, **k: (seen.append(_probe(cache_root)), "")[1]

    ok, err = job.cache_file("cert.pem", b"-----BEGIN CERTIFICATE-----", service_id="default-server")

    assert (ok, err) == (True, "")
    assert (job.job_path / "default-server" / "cert.pem").is_file()
    assert seen == [True], "cache_file wrote the file and its row outside the publication lock"


def test_del_cache_holds_the_publication_lock(job, cache_root):
    """A withdrawal a push rolls back is a retired certificate the instance keeps serving."""
    target = job.job_path / "default-server" / "cert.pem"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"retired")
    seen = []
    job.db.delete_job_cache.side_effect = lambda *a, **k: (seen.append(_probe(cache_root)), "")[1]

    ok, _ = job.del_cache("cert.pem", service_id="default-server")

    assert ok
    assert seen == [True], "del_cache removed the file outside the publication lock"


def test_restore_cache_holds_the_publication_lock(job, cache_root):
    """A restore rewrites the whole plugin directory; a push mid-restore rolls it back."""
    seen = []
    job.db.get_jobs_cache_files.side_effect = lambda *a, **k: (seen.append(_probe(cache_root)), [])[1]

    assert job.restore_cache(manual=False) is True
    assert seen == [True], "restore_cache rewrote the plugin tree outside the publication lock"


def test_a_write_waits_for_a_publication_in_flight(job, cache_root):
    """The point of the lock: a job cannot write while the tree is being published."""
    fd = os_open((cache_root / CACHE_PUBLICATION_LOCK_NAME).as_posix(), O_CREAT | O_RDWR, 0o660)
    flock(fd, LOCK_EX)
    target = job.job_path / "default-server" / "cert.pem"
    try:
        writer = Thread(target=job.cache_file, args=("cert.pem", b"fresh"), kwargs={"service_id": "default-server"})
        writer.start()
        writer.join(0.5)
        assert writer.is_alive(), "the write did not wait for the publication in flight"
        assert not target.exists()
    finally:
        flock(fd, LOCK_UN)
        os_close(fd)

    writer.join(5)
    assert not writer.is_alive()
    assert target.read_bytes() == b"fresh"


def test_a_stuck_holder_never_enters_the_protected_body(cache_root):
    """`flock` has no timeout; blocking outright would pin every job until Celery killed it."""
    logger = Mock()
    fd = os_open((cache_root / CACHE_PUBLICATION_LOCK_NAME).as_posix(), O_CREAT | O_RDWR, 0o660)
    flock(fd, LOCK_EX)
    try:
        with pytest.raises(RuntimeError, match="publication lock"):
            with cache_publication_lock(logger, timeout=0):
                pytest.fail("entered protected body without the lock")
    finally:
        flock(fd, LOCK_UN)
        os_close(fd)

    assert logger.warning.called
    assert "publication lock" in logger.warning.call_args[0][0]


def test_the_lock_file_is_reserved_so_a_swap_never_replaces_it():
    """`pushswap.is_reserved` skips the reserved prefix, so the swap leaves this file alone.

    Pinned against the Lua constant itself, not against a copy of it: a lock file the swap replaces
    is two processes flocking two different inodes, which is no lock at all -- and the two sides are
    in different languages, so nothing but this assertion would notice the prefix being renamed.
    """
    pushswap = Path(__file__).resolve().parents[3] / "src" / "bw" / "lua" / "bunkerweb" / "pushswap.lua"
    reserved = search(r'pushswap\.RESERVED_PREFIX\s*=\s*"([^"]+)"', pushswap.read_text(encoding="utf-8"))
    assert reserved, "pushswap.RESERVED_PREFIX is no longer a literal assignment"
    assert CACHE_PUBLICATION_LOCK_NAME.startswith(reserved.group(1))


def test_wait_budget_does_not_claim_to_outlast_every_push():
    """The bounded network phases alone can exceed the wait; failure must stay closed."""
    from ApiCaller import BUSY_ATTEMPTS, BUSY_RETRY_DELAY, folder_push_timeout

    connect, read = folder_push_timeout(30, 10_000)
    write = read  # ApiCaller.send_files defaults the independent body-write budget to the read budget.
    bounded_phases = BUSY_ATTEMPTS * (connect + write + read) + (BUSY_ATTEMPTS - 1) * BUSY_RETRY_DELAY
    assert bounded_phases == 739
    assert CACHE_PUBLICATION_LOCK_WAIT < bounded_phases


def test_an_unusable_cache_root_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "CACHE_PATH", tmp_path / "missing" / "\0bad")
    with pytest.raises(RuntimeError, match="publication lock"):
        with cache_publication_lock(Mock()):
            pytest.fail("entered protected body without the lock")


def test_permanent_flock_failure_does_not_retry(cache_root, monkeypatch):
    monkeypatch.setattr(jobs, "flock", Mock(side_effect=OSError("unsupported")))
    pause = Mock(side_effect=AssertionError("permanent errors must not retry"))
    monkeypatch.setattr(jobs, "sleep", pause)
    with pytest.raises((RuntimeError, OSError)):
        with cache_publication_lock(timeout=600):
            pytest.fail("entered protected body after permanent failure")
    assert jobs.flock.call_count == 1
    pause.assert_not_called()


class SoftTimeLimitExceeded(Exception):
    """Match billiard's Exception inheritance without requiring Celery in the unit venv."""


@pytest.mark.parametrize("phase", ["open", "flock", "sleep"])
@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SoftTimeLimitExceeded, InterruptedError])
def test_acquisition_propagates_interrupts_and_closes_fd(cache_root, monkeypatch, phase, interrupt):
    close = Mock(wraps=jobs.os_close)
    monkeypatch.setattr(jobs, "os_close", close)
    if phase == "open":
        monkeypatch.setattr(jobs, "os_open", Mock(side_effect=interrupt))
    elif phase == "flock":
        monkeypatch.setattr(jobs, "flock", Mock(side_effect=interrupt))
    else:
        monkeypatch.setattr(jobs, "flock", Mock(side_effect=BlockingIOError))
        monkeypatch.setattr(jobs, "sleep", Mock(side_effect=interrupt))
    with pytest.raises(interrupt):
        with cache_publication_lock(timeout=0 if phase == "flock" else 600):
            pytest.fail("interruption was swallowed")
    assert close.call_count == (0 if phase == "open" else 1)


@pytest.mark.parametrize("method", ["cache_file", "del_cache", "restore_cache"])
def test_job_lock_timeout_preserves_disk_and_database(job, cache_root, monkeypatch, method):
    monkeypatch.setattr(jobs, "CACHE_PUBLICATION_LOCK_WAIT", 0)
    target = job.job_path / "cert.pem"
    target.write_bytes(b"old")
    with cache_publication_lock():
        result = (
            getattr(job, method)("cert.pem", b"new")
            if method == "cache_file"
            else (job.del_cache("cert.pem") if method == "del_cache" else job.restore_cache())
        )
    assert (result if method == "restore_cache" else result[0]) is False
    assert target.read_bytes() == b"old"
    assert job.db.mock_calls == []


def test_contention_deadline_uses_monotonic_time(cache_root, monkeypatch):
    monkeypatch.setattr(jobs, "monotonic", Mock(side_effect=[10, 10, 11]))
    monkeypatch.setattr(jobs, "time", Mock(side_effect=AssertionError("wall clock used")))
    monkeypatch.setattr(jobs, "flock", Mock(side_effect=BlockingIOError))
    pause = Mock()
    monkeypatch.setattr(jobs, "sleep", pause)
    with pytest.raises(RuntimeError, match="publication lock"):
        with cache_publication_lock(timeout=1):
            pytest.fail("entered protected body after deadline")
    assert jobs.flock.call_count == 2
    pause.assert_called_once_with(0.05)
