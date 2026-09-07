"""A cache directory must survive a restore that fails halfway.

`Job.restore_cache` used to `rmtree()` the target and only then extract into it, so an archive that
failed to open -- or a process killed between the two -- left the plugin with an EMPTY directory and
no way back. For Let's Encrypt that is accounts/, archive/ and the live/ symlinks. The comment the
code carried said as much ("rmtree() above already wiped extract_path"), and pushed the problem onto
every caller through `self.restore_ok`.

Port of dev `63a7f6a4d`: the extraction is staged in a sibling directory and renamed into place, a
journal records the swap so an interrupted one is rolled back on the next run, and the stale-file
sweep no longer runs after a failed restore.
"""

from io import BytesIO
from json import dumps
from logging import ERROR
from tarfile import SYMTYPE, TarInfo, open as tar_open
from unittest.mock import Mock

import pytest

import cache_restore
from cache_restore import recover_directory
from jobs import Job


def _archive(entries, symlinks=None) -> bytes:
    """A .tgz payload holding ``{name: content}`` plus optional ``{name: target}`` symlinks."""
    raw = BytesIO()
    with tar_open(fileobj=raw, mode="w:gz") as tar:
        for name, content in entries.items():
            info = TarInfo(name)
            info.size = len(content)
            tar.addfile(info, BytesIO(content))
        for name, target in (symlinks or {}).items():
            info = TarInfo(name)
            info.type = SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return raw.getvalue()


@pytest.fixture
def job(tmp_path):
    """A Job pointed at a temporary plugin directory (``__init__`` hardcodes /var/cache/bunkerweb)."""
    instance = Job.__new__(Job)
    instance.job_path = tmp_path / "letsencrypt"
    instance.job_name = "certbot-new"
    instance.logger = Mock()
    instance.db = Mock()
    return instance


def test_a_failed_extraction_keeps_the_previous_directory(job):
    """The regression: a corrupt archive used to publish an empty directory."""
    live = job.job_path / "example.com"
    live.mkdir(parents=True)
    (live / "privkey.pem").write_bytes(b"the only copy")

    job.db.get_jobs_cache_files.return_value = [
        {"service_id": "example.com", "file_name": "certs.tgz", "job_name": "certbot-new", "data": b"not a gzip stream"}
    ]

    assert job.restore_cache(manual=False) is False
    assert (live / "privkey.pem").read_bytes() == b"the only copy", "a failed extraction destroyed the previous certificate"


def test_a_successful_extraction_replaces_the_directory(job):
    """The swap still has to actually publish."""
    live = job.job_path / "example.com"
    live.mkdir(parents=True)
    (live / "stale.pem").write_bytes(b"old")

    job.db.get_jobs_cache_files.return_value = [
        {"service_id": "example.com", "file_name": "certs.tgz", "job_name": "certbot-new", "data": _archive({"fullchain.pem": b"new"})}
    ]

    assert job.restore_cache(manual=False) is True
    assert (live / "fullchain.pem").read_bytes() == b"new"
    assert not (live / "stale.pem").exists()
    assert not list(job.job_path.glob(".example.com.cache-*")), "the transaction left its journal or backup behind"


def test_the_sweep_does_not_run_after_a_failed_restore(job):
    """A failed row leaves the previous generation on disk; sweeping it would delete that."""
    job.job_path.mkdir(parents=True)
    (job.job_path / "accounts").mkdir()
    (job.job_path / "accounts" / "regr.json").write_bytes(b"account")

    job.db.get_jobs_cache_files.return_value = [
        {"service_id": "example.com", "file_name": "certs.tgz", "job_name": "certbot-new", "data": b"not a gzip stream"}
    ]

    assert job.restore_cache(manual=False) is False
    assert (job.job_path / "accounts" / "regr.json").exists(), "the sweep ran after a failed restore and deleted the account tree"


def test_a_cache_row_cannot_escape_its_plugin_directory(job, tmp_path):
    """`file_name` comes from the database; a traversing one used to be joined and written blindly."""
    outside = tmp_path / "outside.pem"
    job.db.get_jobs_cache_files.return_value = [{"service_id": "", "file_name": "../outside.pem", "job_name": "certbot-new", "data": b"escaped"}]

    assert job.restore_cache(manual=False) is False
    assert not outside.exists(), "a cache row wrote outside its plugin directory"


def test_an_absolute_cache_row_stays_inside_its_plugin_directory(job, tmp_path):
    """`Path.joinpath` lets an absolute member REPLACE the plugin root, with no `..` to notice."""
    victim = tmp_path / "geoip" / "asn.mmdb"
    victim.parent.mkdir(parents=True)
    victim.write_bytes(b"another plugin's cache")
    job.db.get_jobs_cache_files.return_value = [{"service_id": "", "file_name": victim.as_posix(), "job_name": "certbot-new", "data": b"overwritten"}]

    assert job.restore_cache(manual=False) is False
    assert victim.read_bytes() == b"another plugin's cache", "a cache row overwrote another plugin's cache file"


def test_an_interrupted_publication_is_rolled_back(tmp_path, monkeypatch):
    """A retained backup plus its journal is what a process killed mid-swap leaves behind."""
    monkeypatch.setattr(cache_restore, "FOLDER_ROOTS", (tmp_path.resolve(),))
    target = tmp_path / "plugins"
    target.mkdir()
    (target / "half-written").write_bytes(b"partial")
    backup = tmp_path / ".plugins.cache-backup"
    backup.mkdir()
    (backup / "good.conf").write_bytes(b"the previous generation")
    (tmp_path / ".plugins.cache-journal").write_bytes(dumps({"had_target": True}).encode())

    recover_directory(target)

    assert (target / "good.conf").read_bytes() == b"the previous generation"
    assert not (target / "half-written").exists()
    assert not backup.exists() and not (tmp_path / ".plugins.cache-journal").exists()


def test_half_a_crs_pair_is_refused(tmp_path):
    """The rendered ModSecurity config is the intersection of the manifest and the directory."""
    instance = Job.__new__(Job)
    instance.job_path = tmp_path / "modsecurity"
    instance.job_name = "download-crs-plugins"
    instance.logger = Mock()
    instance.db = Mock()
    live = instance.job_path / "crs" / "plugins"
    live.mkdir(parents=True)
    (live / "installed-config.conf").write_bytes(b"the previous plugin set")
    manifest = instance.job_path / "crs-plugins.json"
    manifest.write_bytes(b'{"www.example.com": []}')

    # The manifest row without its archive row: the pair is incomplete.
    instance.db.get_jobs_cache_files.return_value = [
        {"service_id": "", "file_name": "crs-plugins.json", "job_name": "download-crs-plugins", "data": b'{"www.example.com": ["fake"]}'}
    ]

    assert instance.restore_cache(manual=False) is False
    assert (live / "installed-config.conf").exists()
    assert manifest.read_bytes() == b'{"www.example.com": []}', "half a CRS pair was published on its own"


def test_the_crs_pair_is_published_together(tmp_path, monkeypatch):
    """Both members land, or neither does: the archive's transaction carries the manifest."""
    instance = Job.__new__(Job)
    instance.job_path = tmp_path / "modsecurity"
    instance.job_name = "download-crs-plugins"
    instance.logger = Mock()
    instance.db = Mock()
    live = instance.job_path / "crs" / "plugins"
    live.mkdir(parents=True)
    manifest = instance.job_path / "crs-plugins.json"
    manifest.write_bytes(b'{"www.example.com": []}')
    monkeypatch.setattr(cache_restore, "FOLDER_ROOTS", (tmp_path.resolve(),))

    archive_name = f"folder:{live}.tgz"
    instance.db.get_jobs_cache_files.return_value = [
        {"service_id": "", "file_name": "crs-plugins.json", "job_name": "download-crs-plugins", "data": b'{"www.example.com": ["fake"]}'},
        {"service_id": "", "file_name": archive_name, "job_name": "download-crs-plugins", "data": _archive({"fake/plugin-config.conf": b"rules"})},
    ]

    assert instance.restore_cache(manual=False) is True
    assert (live / "fake" / "plugin-config.conf").read_bytes() == b"rules"
    assert manifest.read_bytes() == b'{"www.example.com": ["fake"]}'


def test_a_dangling_symlink_is_finally_swept(job, tmp_path):
    """`is_file()` is False for a broken link, so the sweep skipped it on every run, forever.

    A stale `live/*` link left by a certificate that was deleted is exactly this shape, and the
    cache tree is tarred to the instances with it. `Path.unlink()` never follows a link, so the two
    branches only ever act on the link itself -- the case below pins that.
    """
    job.job_path.mkdir(parents=True)
    dangling = job.job_path / "live.pem"
    dangling.symlink_to(tmp_path / "deleted-by-a-previous-run.pem")

    job.db.get_jobs_cache_files.return_value = [{"service_id": "shared", "file_name": "kept.pem", "job_name": "certbot-new", "data": b"kept"}]

    assert job.restore_cache(manual=False) is True
    assert not dangling.is_symlink(), "the dangling symlink survived the sweep"


def test_a_stale_symlink_is_unlinked_without_touching_its_target(job, tmp_path):
    """A symlink to a DIRECTORY is new territory: `iterdir()` followed it, so a non-empty one was
    kept forever. It is unlinked now -- the link, never what it points at."""
    job.job_path.mkdir(parents=True)
    outside = tmp_path / "real"
    outside.mkdir()
    (outside / "payload.pem").write_bytes(b"pointed at")
    stale = job.job_path / "live"
    stale.symlink_to(outside)

    job.db.get_jobs_cache_files.return_value = [{"service_id": "shared", "file_name": "kept.pem", "job_name": "certbot-new", "data": b"kept"}]

    assert job.restore_cache(manual=False) is True
    assert not stale.is_symlink(), "the stale symlink survived the sweep"
    assert (outside / "payload.pem").read_bytes() == b"pointed at", "the sweep deleted what the symlink pointed at"


def test_a_symlink_carried_by_the_archive_survives_the_restore(job):
    """Let's Encrypt ships `live/* -> archive/*` INSIDE the archive: the staged extraction has to
    keep the link (that is what `tar_filter="auto"` is for) and the sweep must not then remove it."""
    job.db.get_jobs_cache_files.return_value = [
        {
            "service_id": "example.com",
            "file_name": "certs.tgz",
            "job_name": "certbot-new",
            "data": _archive({"archive/cert1.pem": b"chain"}, symlinks={"live.pem": "archive/cert1.pem"}),
        }
    ]

    assert job.restore_cache(manual=False) is True
    link = job.job_path / "example.com" / "live.pem"
    assert link.is_symlink(), "the archive's symlink did not survive the restore"
    assert link.read_bytes() == b"chain"


def test_an_unreadable_journal_still_rolls_back(tmp_path, monkeypatch):
    """A truncated journal must not wedge the plugin: the backup alone carries the previous set.

    `write_atomic` does not fsync, so a power cut can leave a renamed-but-empty journal. Raising on
    it failed the whole plugin's restore before any row was touched -- and since the sweep only runs
    on a successful restore, nothing ever deleted the journal, so every later run failed the same
    way while certbot refused to re-cache (`restore_ok` stays False).
    """
    monkeypatch.setattr(cache_restore, "FOLDER_ROOTS", (tmp_path.resolve(),))
    target = tmp_path / "plugins"
    target.mkdir()
    (target / "half-written").write_bytes(b"partial")
    backup = tmp_path / ".plugins.cache-backup"
    backup.mkdir()
    (backup / "good.conf").write_bytes(b"the previous generation")
    (tmp_path / ".plugins.cache-journal").write_bytes(b"")  # truncated by the power cut

    recover_directory(target)

    assert (target / "good.conf").read_bytes() == b"the previous generation"
    assert not (tmp_path / ".plugins.cache-journal").exists(), "the unreadable journal was left to fail every later run"


def test_an_unreadable_journal_says_so_when_a_companion_cannot_follow(tmp_path, monkeypatch, caplog):
    """DEV-2b4 / Criticos round 2 C2: the degraded path is safe for the DIRECTORY only.

    The companion's previous generation lives ONLY in the journal (`publish` base64s it into
    `state["data"]`), so an unreadable journal rolls the directory back and leaves the companion
    where the interrupted publication put it -- one generation ahead. For the CRS pair that is
    exactly the manifest/directory mismatch `_check_pair` exists to catch, and nothing raises: the
    rendered ModSecurity config is their intersection. This pins the ERROR that makes it visible,
    and records the mismatch as a KNOWN state rather than an assumed-safe one.
    """
    monkeypatch.setattr(cache_restore, "FOLDER_ROOTS", (tmp_path.resolve(),))
    target = tmp_path / "plugins"
    target.mkdir()
    (target / "new.conf").write_bytes(b"the interrupted generation")
    companion = tmp_path / "plugins.json"
    companion.write_bytes(b'{"manifest": "NEW"}')  # already swapped by the interrupted publication
    backup = tmp_path / ".plugins.cache-backup"
    backup.mkdir()
    (backup / "old.conf").write_bytes(b"the previous generation")
    (tmp_path / ".plugins.cache-journal").write_bytes(b"")

    with caplog.at_level("WARNING"):
        recover_directory(target, companion)

    # The directory went back; the companion could not.
    assert (target / "old.conf").exists()
    assert not (target / "new.conf").exists()
    assert companion.read_bytes() == b'{"manifest": "NEW"}'
    # `levelno`, not `levelname`: `logger.py` renames the levels to emoji.
    errors = [record for record in caplog.records if record.levelno >= ERROR]
    assert errors, "the mismatched pair was left silent"
    assert str(companion) in errors[0].getMessage()
    assert "one generation ahead" in errors[0].getMessage()


def test_an_unreadable_journal_with_no_companion_does_not_cry_wolf(tmp_path, monkeypatch, caplog):
    """No companion, no possible desync: a WARNING, not an ERROR."""
    monkeypatch.setattr(cache_restore, "FOLDER_ROOTS", (tmp_path.resolve(),))
    target = tmp_path / "plugins"
    target.mkdir()
    backup = tmp_path / ".plugins.cache-backup"
    backup.mkdir()
    (backup / "old.conf").write_bytes(b"the previous generation")
    (tmp_path / ".plugins.cache-journal").write_bytes(b"")

    with caplog.at_level("WARNING"):
        recover_directory(target, companion=False)

    assert not [record for record in caplog.records if record.levelno >= ERROR]
