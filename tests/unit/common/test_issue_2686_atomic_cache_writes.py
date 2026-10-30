"""A cache file written in place left a truncated certificate behind when the write was interrupted.

Job cache files (the default server certificate and key among them) were written straight onto their
final path, so a write that died midway (full disk, killed job) left a partial PEM that nginx then refused
to load ("cannot load certificate"). Writes now go through a temporary file renamed over the target. The
tests make a write fail after the first bytes with a file size limit and assert the previous content, or
the absence of the file, is what remains.

Refs: #2686.
"""

import resource
import signal
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

import jobs

OLD = b"-----BEGIN CERTIFICATE-----\nold\n-----END CERTIFICATE-----\n"
NEW = b"x" * 200_000
LIMIT = 4096


@contextmanager
def disk_fills_after(limit):
    """Every write past ``limit`` bytes into one file fails with ``OSError`` (EFBIG), after the first bytes landed."""
    old_handler = signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, hard))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
        signal.signal(signal.SIGXFSZ, old_handler)


@pytest.fixture
def job(tmp_path):
    instance = object.__new__(jobs.Job)
    instance.job_path = tmp_path / "plugin"
    instance.job_path.mkdir()
    instance.job_name = "default-server-cert"
    instance.db = Mock()
    instance.db.upsert_job_cache.return_value = ""
    instance.logger = Mock()
    return instance


def test_an_interrupted_overwrite_keeps_the_previous_file(job):
    target = job.job_path / "default-server-cert.pem"
    target.write_bytes(OLD)

    with disk_fills_after(LIMIT), pytest.raises(OSError):
        job.cache_file("default-server-cert.pem", NEW)

    assert target.read_bytes() == OLD
    job.db.upsert_job_cache.assert_not_called()


def test_an_interrupted_first_write_leaves_no_partial_file(job):
    target = job.job_path / "default-server-cert.pem"

    with disk_fills_after(LIMIT), pytest.raises(OSError):
        job.cache_file("default-server-cert.pem", NEW)

    assert not target.exists()


def test_a_completed_overwrite_replaces_the_content_and_keeps_the_mode(job):
    target = job.job_path / "default-server-cert.key"
    target.write_bytes(OLD)
    target.chmod(0o600)

    assert job.cache_file("default-server-cert.key", b"fresh") == (True, "")

    assert target.read_bytes() == b"fresh"
    assert target.stat().st_mode & 0o777 == 0o600
