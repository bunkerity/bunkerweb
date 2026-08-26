"""`ensure_backup_dir` — the backup directory must end up owned by the user that rotates,
and it must NEVER be reached through a symlink.

Two contracts, and the second one is why this file is long.

**Rotation.** `bwcli plugin backup save` runs as root on a package install; the Celery worker
that runs `backup-data` (and therefore `rotate_backups`) runs as nginx. Whoever creates
/var/lib/bunkerweb/backups first owns it, and unlinking a file needs write+execute on the
DIRECTORY, not on the file. A root-created directory therefore killed rotation outright:

    PermissionError: [Errno 13] Permission denied: '.../backup-sqlite-....zip'

raised from `rotate_backups`, so the backup count grew past BACKUP_ROTATION forever and the
only trace was in the worker journal. Reproduced on the Linux integration arm as
`backup;rotation` reporting "Found 8 backups" against an expectation of 7.

**Privilege.** The repair runs as ROOT, and the directory's parent is owned by nginx — the uid
the API, the UI, the worker and the Lua runtime all run as. `Path.mkdir(exist_ok=True)` does
not raise on a symlink-to-directory and `Path.stat()`/`os.chown()` both follow it, so a
path-based chown would let a compromised nginx point `backups` at `/etc` and have the
operator's next root `bwcli plugin backup save` hand it `/etc` — then `/etc/ld.so.preload`.
An `is_symlink()` pre-check cannot close it: the swap can land between the check and the
chown. Only `O_NOFOLLOW` + `fchown` on the held descriptor does.

The ownership *outcome* needs root, so those three cases skip outside a root runner. The
symlink refusal and the fchown wiring are asserted with spies instead and run everywhere,
including CI — `test_a_real_directory_is_still_chowned` exists so the adversarial cases cannot
pass vacuously by the function simply never chowning anything.
"""

import os
import sys
from pathlib import Path

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402
from backup import ensure_backup_dir  # noqa: E402

needs_root = pytest.mark.skipif(os.geteuid() != 0, reason="chown requires root")


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Point the product state directory -- the reference owner -- inside tmp_path.

    `ensure_backup_dir` aligns with `DB_LOCK_FILE.parent` (/var/lib/bunkerweb), deliberately
    not with the backup directory's own parent: a custom BACKUP_DIRECTORY under a root-owned
    parent would otherwise be aligned to root, which is the bug being fixed.
    """
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(backup, "DB_LOCK_FILE", state / "db.lock")
    return state


class TestDirectoryCreation:
    def test_a_missing_directory_is_created(self, tmp_path):
        target = tmp_path / "backups"
        assert ensure_backup_dir(target) == target
        assert target.is_dir()

    def test_missing_parents_are_created_too(self, tmp_path):
        target = tmp_path / "var" / "lib" / "bunkerweb" / "backups"
        ensure_backup_dir(target)
        assert target.is_dir()

    def test_an_existing_directory_and_its_content_survive(self, tmp_path):
        target = tmp_path / "backups"
        target.mkdir()
        kept = target / "backup-sqlite-2026-08-26_07-54-04.zip"
        kept.write_bytes(b"payload")
        ensure_backup_dir(target)
        assert kept.read_bytes() == b"payload"

    def test_calling_it_twice_is_not_an_error(self, tmp_path):
        target = tmp_path / "backups"
        ensure_backup_dir(target)
        ensure_backup_dir(target)
        assert target.is_dir()


class TestOwnershipAlignment:
    @needs_root
    def test_a_directory_created_as_root_takes_the_state_directory_owner(self, tmp_path, state_dir):
        os.chown(state_dir, 12345, 12345)

        target = tmp_path / "bunkerweb" / "backups"
        ensure_backup_dir(target)

        stat = target.stat()
        assert (stat.st_uid, stat.st_gid) == (12345, 12345)

    @needs_root
    def test_a_directory_left_root_owned_by_an_earlier_run_is_repaired(self, tmp_path, state_dir):
        os.chown(state_dir, 12345, 12345)
        target = tmp_path / "bunkerweb" / "backups"
        target.mkdir(parents=True)
        os.chown(target, 0, 0)

        ensure_backup_dir(target)

        stat = target.stat()
        assert (stat.st_uid, stat.st_gid) == (12345, 12345)

    @needs_root
    def test_a_custom_directory_under_a_root_owned_parent_is_still_repaired(self, tmp_path, state_dir):
        """The reason the reference is the state directory and not `directory.parent`.

        Aligning with the parent here would chown to root and leave rotation exactly as broken
        as it was before this function existed.
        """
        os.chown(state_dir, 12345, 12345)
        mount = tmp_path / "mnt"
        mount.mkdir()
        os.chown(mount, 0, 0)
        target = mount / "backups"

        ensure_backup_dir(target)

        stat = target.stat()
        assert (stat.st_uid, stat.st_gid) == (12345, 12345)


class TestItNeverFollowsASymlink:
    """The privilege-escalation guard. These run without root: the spies see the decision."""

    def _as_root_with_spies(self, monkeypatch, owner_uid=12345, owner_gid=12345):
        monkeypatch.setattr(backup, "geteuid", lambda: 0)
        calls = []
        monkeypatch.setattr(backup, "fchown", lambda *args: calls.append(args))

        class _Owner:
            st_uid = owner_uid
            st_gid = owner_gid

        monkeypatch.setattr(backup, "os_stat", lambda _path: _Owner())
        return calls

    def test_a_real_directory_is_still_chowned(self, tmp_path, monkeypatch):
        """Anti-vacuity: the refusal tests below only mean something if this one passes."""
        calls = self._as_root_with_spies(monkeypatch)

        target = tmp_path / "backups"
        ensure_backup_dir(target)

        assert len(calls) == 1
        fd, uid, gid = calls[0]
        assert (uid, gid) == (12345, 12345)
        assert isinstance(fd, int)

    def test_a_symlinked_backup_directory_is_never_chowned(self, tmp_path, monkeypatch):
        """The attack: nginx owns the parent, so it can replace `backups` with a symlink."""
        calls = self._as_root_with_spies(monkeypatch)

        victim = tmp_path / "victim"
        victim.mkdir()
        before = victim.stat()

        parent = tmp_path / "bunkerweb"
        parent.mkdir()
        target = parent / "backups"
        target.symlink_to(victim, target_is_directory=True)

        ensure_backup_dir(target)

        assert calls == [], "fchown reached a symlinked directory — the O_NOFOLLOW guard is gone"
        after = victim.stat()
        assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)

    def test_the_symlink_itself_is_left_alone(self, tmp_path, monkeypatch):
        """`lchown` would chown the link and leave rotation broken; nothing may do that."""
        self._as_root_with_spies(monkeypatch)

        victim = tmp_path / "victim"
        victim.mkdir()
        target = tmp_path / "backups"
        target.symlink_to(victim, target_is_directory=True)
        before = target.lstat()

        ensure_backup_dir(target)

        after = target.lstat()
        assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)
        assert target.is_symlink()

    def test_a_symlink_to_a_file_never_reaches_the_chown(self, tmp_path, monkeypatch):
        """A swap pointing at something that is not a directory dies on the mkdir, not later.

        `Path.mkdir(exist_ok=True)` stays silent for a symlink-to-DIRECTORY -- which is why the
        O_NOFOLLOW guard has to exist -- but raises `FileExistsError` when the target is not a
        directory. That predates this function and is the right answer (you cannot write
        archives into a file); what matters here is that no chown is reached either way.
        """
        calls = self._as_root_with_spies(monkeypatch)

        victim = tmp_path / "victim"
        victim.write_text("not a directory")
        before = victim.stat()
        target = tmp_path / "backups"
        target.symlink_to(victim)

        with pytest.raises(FileExistsError):
            ensure_backup_dir(target)

        assert calls == []
        after = victim.stat()
        assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)

    def test_the_backup_still_proceeds_after_a_refusal(self, tmp_path, monkeypatch):
        """A refused chown is a warning: the caller gets its path back and writes its archive."""
        self._as_root_with_spies(monkeypatch)

        victim = tmp_path / "victim"
        victim.mkdir()
        target = tmp_path / "backups"
        target.symlink_to(victim, target_is_directory=True)

        assert ensure_backup_dir(target) == target

    def test_an_impossible_chown_does_not_fail_the_backup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup, "geteuid", lambda: 0)

        def refuse(*args):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(backup, "fchown", refuse)

        target = tmp_path / "backups"
        assert ensure_backup_dir(target) == target
        assert target.is_dir()

    def test_a_missing_state_directory_does_not_fail_the_backup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup, "geteuid", lambda: 0)
        monkeypatch.setattr(backup, "DB_LOCK_FILE", tmp_path / "nope" / "db.lock")

        target = tmp_path / "backups"
        assert ensure_backup_dir(target) == target
        assert target.is_dir()


class TestUnlinkIsWhatThisBuys:
    def test_the_owner_of_the_directory_can_unlink_a_file_it_does_not_own(self, tmp_path):
        """The whole point: rotation unlinks files it did not write.

        POSIX grants unlink on directory permissions, not file ownership, so aligning the
        DIRECTORY is enough and the archives may stay root-owned.
        """
        target = tmp_path / "backups"
        ensure_backup_dir(target)
        victim = target / "backup-sqlite-2026-08-26_07-54-04.zip"
        victim.write_bytes(b"payload")
        victim.chmod(0o400)

        victim.unlink()

        assert not victim.exists()
