"""The stale-file sweep must not delete another job's write in progress.

`Job.restore_cache` finishes by removing every file in the plugin's cache directory that the
database does not know about. `_write_atomic` stages its data in that same directory, so the sweep
used to unlink a concurrent job's temporary — three times running, which is exactly the retry
budget in `_write_atomic`, so the write failed outright and the instance silently lost the file.

Seen live: `Failed to materialize cache 'asn.mmdb': [Errno 2] No such file or directory:
'/var/cache/bunkerweb/geoip/.asn.mmdb.doounvlh'`, one second after geoip-asn restored into the same
directory.
"""

from os import utime
from pathlib import Path
from time import time
from unittest.mock import Mock

import pytest

from jobs import ATOMIC_TMP_GRACE_SECONDS, ATOMIC_TMP_SUFFIX, Job, _write_atomic


@pytest.fixture
def job(tmp_path):
    """A Job whose database knows about no cache files, so the sweep considers everything stale.

    Built without ``__init__``: that hardcodes ``/var/cache/bunkerweb/<plugin>`` and creates it, so
    there is no way to point a real instance at a temporary directory.
    """
    instance = Job.__new__(Job)
    instance.job_path = tmp_path / "geoip"
    instance.job_name = "geoip-asn"
    instance.logger = Mock()
    instance.db = Mock()
    # One row, so the sweep runs at all: `restore_cache` now leaves the directory ALONE when the
    # plugin has no cache rows, because an empty row set means the cache is unknown rather than
    # unused (deleting one row in the web UI used to destroy the Let's Encrypt account tree).
    # Neither test below is about emptiness -- it was only the fixture's way of making everything
    # look stale -- and neither file they create is in this row set, so both are still swept.
    #
    # The service_id is load-bearing: a row without one restores into job_path itself, and
    # `restore_cache` adds every restored file's PARENT to the ignore list. That would be job_path,
    # so the sweep would skip the whole directory. Measured, not guessed: with `service_id: ""`
    # both tests below fail.
    instance.db.get_jobs_cache_files.return_value = [
        {"service_id": "shared", "file_name": "asn.mmdb", "job_name": "geoip-asn", "data": b"payload"}
    ]
    return instance


def test_write_atomic_marks_its_temporary(tmp_path):
    """The sweep recognises temporaries by suffix, so the writer has to apply one.

    A leading dot would not do: `.key` files are genuine cache entries that get pushed to instances.
    """
    target = tmp_path / "asn.mmdb"
    staged = []

    # os.replace is what moves the temporary into place; capture the directory just before it does.
    import jobs as jobs_module

    original_replace = jobs_module.replace

    def _spy(src, dst):
        staged.append(Path(src).name)
        return original_replace(src, dst)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(jobs_module, "replace", _spy)
    try:
        _write_atomic(target, b"payload")
    finally:
        monkeypatch.undo()

    assert target.read_bytes() == b"payload"
    assert staged and staged[0].endswith(ATOMIC_TMP_SUFFIX), f"temporary was not marked: {staged}"
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(ATOMIC_TMP_SUFFIX)], "temp left behind"


def test_a_live_temporary_survives_the_sweep(job):
    """The regression: this file belongs to a job that is still writing it."""
    job.job_path.mkdir(parents=True, exist_ok=True)
    live = job.job_path / f".asn.mmdb.doounvlh{ATOMIC_TMP_SUFFIX}"
    live.write_bytes(b"half-written")

    job.restore_cache(manual=False)

    assert live.exists(), "the sweep deleted a concurrent job's in-flight atomic write"


def test_an_orphaned_temporary_is_reaped(job):
    """A temp left by a killed process must not linger — the cache ships to instances as a tar."""
    job.job_path.mkdir(parents=True, exist_ok=True)
    orphan = job.job_path / f".asn.mmdb.deadbeef{ATOMIC_TMP_SUFFIX}"
    orphan.write_bytes(b"abandoned")
    old = time() - (ATOMIC_TMP_GRACE_SECONDS + 60)
    utime(orphan, (old, old))

    job.restore_cache(manual=False)

    assert not orphan.exists(), "an orphaned temporary was kept forever"


def test_ordinary_stale_files_are_still_removed(job):
    """The sweep's actual job — the temp guard must not blanket-disable it."""
    job.job_path.mkdir(parents=True, exist_ok=True)
    stale = job.job_path / "country.mmdb"
    stale.write_bytes(b"no longer in the database")

    job.restore_cache(manual=False)

    assert not stale.exists(), "the sweep stopped removing genuinely stale files"


def test_no_cache_rows_deletes_nothing(job):
    """An empty row set means the cache is UNKNOWN, not that every file on disk is unused.

    `restore_cache` deletes any file the database does not list. With no rows that is every file,
    while the job still returns success -- so deleting a single cache row in the web UI wiped the
    Let's Encrypt `accounts/`, `archive/` and `live/` tree, and the run reported that it worked.

    The accepted consequence, deliberately not asserted away: a plugin with genuinely zero rows now
    never sweeps, so orphaned files accumulate there. Lingering files are recoverable disk waste; a
    destroyed ACME account tree is not.
    """
    job.db.get_jobs_cache_files.return_value = []
    job.job_path.mkdir(parents=True, exist_ok=True)
    account = job.job_path / "accounts" / "acme-v02.api.letsencrypt.org" / "directory" / "deadbeef"
    account.mkdir(parents=True)
    (account / "private_key.json").write_bytes(b"key material")
    loose = job.job_path / "country.mmdb"
    loose.write_bytes(b"not in the database either")

    assert job.restore_cache(manual=False) is True

    assert (account / "private_key.json").exists(), "the ACME account key was deleted by a sweep with no cache rows"
    assert loose.exists(), "the sweep ran despite the plugin having no cache rows"
