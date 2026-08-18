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
    instance.db.get_jobs_cache_files.return_value = []
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
