"""Recoverable, same-filesystem replacement of cached directories.

Ported from dev `63a7f6a4d`. The mTLS half of that commit (`restore_mtls_cache`) is deliberately
absent: 1.7 has no `core/mtls/jobs/` at all -- the centralized-certificates chantier turned
`MTLS_CA_CERTIFICATE` into a path, so there is no `client-cert` job and no `mtls` cache pair to
recover. Everything else applies as-is, because the loss it prevents is 1.7's too: `restore_cache`
and the scheduler's `generate_caches` both `rmtree()` a cache directory and only then extract into
it, so an extraction that fails -- or a process killed between the two -- leaves the plugin with an
EMPTY directory and no way back. For Let's Encrypt that is the accounts, archives and live
symlinks.
"""

from io import BytesIO
from base64 import b64decode, b64encode
from json import dumps, loads
from os import replace, walk
from pathlib import Path
from shutil import rmtree
from stat import S_IMODE
from tarfile import open as tar_open
from tempfile import NamedTemporaryFile, mkdtemp

from common_utils import safe_tar_extractall  # type: ignore
from logger import getLogger  # type: ignore

CACHE_ROOT = Path("/var/cache/bunkerweb")
RESOLVED_CACHE_ROOT = CACHE_ROOT.resolve()
CONFIG_ROOT = Path("/etc/bunkerweb/configs")
RESOLVED_CONFIG_ROOT = CONFIG_ROOT.resolve()
# The scheduler's failover backup is a folder: cache row rooted here, not under the cache root.
TMP_ROOT = Path("/var/tmp/bunkerweb")
RESOLVED_TMP_ROOT = TMP_ROOT.resolve()
# Where a folder: cache row may publish. checked_cache_path keeps a regular entry inside its
# plugin directory, but a folder: row carries its own absolute target and a publication renames a
# whole directory into place, so the target is checked rather than trusted.
FOLDER_ROOTS = (RESOLVED_CACHE_ROOT, RESOLVED_CONFIG_ROOT, RESOLVED_TMP_ROOT)

# `write_atomic` drops its scratch file next to the target, where `Job.restore_cache`'s stale-file
# sweep also runs. The sweep deletes anything it does not recognise, so the temporary needs a marker
# it can match on: a leading dot is not enough, because `.key` files are genuine cache entries that
# get pushed to instances. Defined here rather than in `jobs` because `jobs` imports this module.
ATOMIC_TMP_SUFFIX = ".bw-tmp"


def write_atomic(target: Path, data: bytes) -> None:
    """Replace one file without exposing partial writes or following its symlink."""
    target = _check_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = S_IMODE(target.lstat().st_mode) if target.exists() else None
    for attempt in range(3):
        _check_path(target)
        with NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=ATOMIC_TMP_SUFFIX, delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            tmp_path = Path(tmp.name)
        try:
            if mode is not None:
                tmp_path.chmod(mode)
            _check_path(target)
            replace(tmp_path, target)
            return
        except FileNotFoundError:
            if attempt == 2:
                raise
            _check_path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
        finally:
            tmp_path.unlink(missing_ok=True)


LOGGER = getLogger("CACHE-RESTORE")


def _check_path(path: Path) -> Path:
    roots = ((CACHE_ROOT, RESOLVED_CACHE_ROOT), (CONFIG_ROOT, RESOLVED_CONFIG_ROOT))
    if not path.is_absolute() or path == path.parent or any(path in pair for pair in roots) or ".." in path.parts:
        raise ValueError(f"Invalid cache path: {path}")
    # Container images intentionally link this installed root to /data/cache.
    # Resolve that trusted indirection once, but reject links below it.
    for installed, resolved in roots:
        if installed in path.parents:
            path = resolved / path.relative_to(installed)
            break
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError(f"Cache path traverses a symlink: {path}")
    return path


def checked_cache_path(root: Path, *parts) -> Path:
    """Validate a regular cache entry before reads, writes or existence checks."""
    root = _check_path(root)
    target = _check_path(root.joinpath(*parts))
    if root not in target.parents:
        raise ValueError(f"Cache entry is outside its plugin directory: {target}")
    return target


def checked_folder_target(file_name: str) -> Path:
    """Validate a ``folder:`` cache row and return the directory it is allowed to replace.

    The target is returned in the namespace the row carries. The container images link the
    installed cache root to /data/cache, so returning the resolved path would put ignored_dirs in
    one namespace and the sweep, which walks the installed plugin directory, in another: nothing
    would ever match and the sweep would delete the directory that was just extracted. Every
    writer re-checks the path.
    """
    target = Path(file_name.removeprefix("folder:").removesuffix(".tgz"))
    checked = _check_path(target)
    if not any(root in checked.parents for root in FOLDER_ROOTS):
        raise ValueError(f"Folder cache entry is outside the cache roots: {checked}")
    return target


def transaction_markers(target: Path) -> set:
    """The staging artifacts a publication of ``target`` leaves *beside* it.

    They are siblings, not children, so a sweep driven by the extract targets alone unlinks the
    journal of another job's uncommitted publication in the same plugin directory. The directory
    rollback would still work, but the companion payload lives only in that journal.
    """
    return {target.with_name(f".{target.name}.cache-backup"), target.with_name(f".{target.name}.cache-journal")}


def cache_companion(target: Path):
    """The file that must be published in the same transaction as ``target``.

    The rendered ModSecurity configuration is the INTERSECTION of `crs-plugins.json` and the
    plugin directory, so a manifest that survives a rolled-back directory (or the reverse) renders
    a plugin set nobody ever produced.
    """
    if target in (CACHE_ROOT / "modsecurity/crs/plugins", RESOLVED_CACHE_ROOT / "modsecurity/crs/plugins"):
        return RESOLVED_CACHE_ROOT / "modsecurity/crs-plugins.json"
    return None


def recover_directory(target: Path, companion: Path = None, *, keep_journal: bool = False) -> None:
    """A retained backup marks an interrupted publication; restore it before retrying."""
    target = _check_path(target)
    companion = companion or cache_companion(target)
    backup = target.with_name(f".{target.name}.cache-backup")
    journal = target.with_name(f".{target.name}.cache-journal")
    _check_path(backup)
    _check_path(journal)
    if backup.exists() and not backup.is_dir():
        raise ValueError(f"Cache backup is not a directory: {backup}")
    # A journal that cannot be read is not a reason to refuse the recovery: raising here fails the
    # WHOLE plugin's restore (`Job.restore_cache` returns False before restoring any row, which pins
    # `restore_ok` False and stops certbot re-caching), and nothing would ever delete the journal --
    # every later run would take the same exception. `write_atomic` does not fsync, so a power cut
    # can leave a renamed-but-empty journal. Fall back to the backup directory, which carries the
    # previous generation on its own.
    #
    # Safe for the DIRECTORY, and only for it. The COMPANION's previous generation lives ONLY in
    # the journal (`publish` base64s it into `state["data"]`), so an unreadable journal cannot roll
    # it back: the directory goes back one generation and the companion stays where the interrupted
    # publication left it. For the CRS pair that is a manifest one generation ahead of the plugin
    # directory -- the mismatch `_check_pair`/`test_half_a_crs_pair_is_refused` exist to catch, and
    # it is silent, because the rendered config is simply their intersection. Loud on purpose: the
    # caller usually republishes both halves from the database right after (`Job.restore_cache`),
    # so this line is what tells an operator whose pair rows were incomplete why the fleet drifted.
    state = None
    if journal.exists():
        try:
            state = loads(journal.read_bytes())
        except (ValueError, OSError) as exc:
            state = None
            if companion is not None:
                LOGGER.error(
                    f"Unreadable cache publication journal {journal} ({exc}): rolling {target} back to the previous generation, "
                    f"but {companion} cannot be rolled back with it and may be left one generation ahead"
                )
            else:
                LOGGER.warning(f"Unreadable cache publication journal {journal} ({exc}): rolling {target} back to the previous generation")
    if state == {"committed": True}:
        if backup.exists():
            rmtree(backup)
        journal.unlink()
        return
    if state is None and backup.exists() and keep_journal:
        state = {"had_target": True}
        write_atomic(journal, dumps(state).encode())
    if state is not None:
        if not isinstance(state, dict) or set(state) not in ({"had_target"}, {"data", "had_target"}) or not isinstance(state["had_target"], bool):
            raise ValueError(f"Invalid cache publication journal: {journal}")
        if "data" in state:
            if companion is None:
                raise ValueError(f"Unexpected companion journal for {target}")
            companion = _check_path(companion)
            if state["data"] is None:
                companion.unlink(missing_ok=True)
            else:
                write_atomic(companion, b64decode(state["data"], validate=True))
    if backup.exists():
        if target.exists():
            rmtree(target)
        backup.rename(target)
    elif state and not state["had_target"] and target.exists():
        rmtree(target)
    if not keep_journal:
        journal.unlink(missing_ok=True)


class StagedDirectory:
    """Keep the old directory until the caller commits all related writes.

    Startup recovery rolls back a retained backup, including a crash between the
    two renames. Only this transaction's staging directory is ever cleaned up.
    """

    def __init__(self, target: Path, companion: Path = None, *, keep_journal: bool = False):
        target = _check_path(target)
        self.target = target
        self.companion = _check_path(companion) if companion is not None else None
        self.keep_journal = keep_journal
        recover_directory(target, self.companion, keep_journal=keep_journal)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.backup = target.with_name(f".{target.name}.cache-backup")
        self.journal = target.with_name(f".{target.name}.cache-journal")
        self.path = Path(mkdtemp(prefix=f".{target.name}.cache-staging-", dir=target.parent))
        self.published = False
        self.committed = False

    def __enter__(self):
        return self

    def publish(self, data: bytes = None) -> None:
        _check_path(self.target)
        companion = self.companion
        state = {"had_target": self.target.exists()}
        if companion is not None:
            _check_path(companion)
            state["data"] = b64encode(companion.read_bytes()).decode() if companion.exists() else None
        write_atomic(self.journal, dumps(state).encode())
        if self.target.exists():
            self.target.rename(self.backup)
        try:
            self.path.rename(self.target)
            self.published = True
            if companion is not None:
                write_atomic(companion, data)
        except BaseException:
            recover_directory(self.target, self.companion, keep_journal=self.keep_journal)
            self.published = False
            raise

    def commit(self) -> None:
        # The caller has already committed its database transaction. A cleanup
        # failure must not undo the corresponding live filesystem generation.
        self.committed = True
        if self.journal.exists():
            write_atomic(self.journal, b'{"committed":true}')
        if self.backup.exists():
            rmtree(self.backup)
        self.journal.unlink(missing_ok=True)

    def __exit__(self, *_):
        if not self.committed:
            if self.backup.exists() or self.journal.exists():
                recover_directory(self.target, self.companion, keep_journal=self.keep_journal)
            elif self.published:
                rmtree(self.target)
        if self.path.exists():
            rmtree(self.path)


def restore_directory(target: Path, data: bytes, companion: Path = None, companion_data: bytes = None) -> None:
    with StagedDirectory(target, companion) as staged:
        with tar_open(fileobj=BytesIO(data), mode="r:gz") as tar:
            # tar_filter="auto" keeps 1.7's behaviour: symlinks survive when the archive carries
            # them (Let's Encrypt live/* -> archive/*) and the stricter "data" filter applies to
            # every link-free archive. `safe_tar_extractall` pre-validates every member either way
            # (CVE-2025-4517), which the code this replaces did not.
            safe_tar_extractall(tar, staged.path, tar_filter="auto")
        staged.publish(companion_data)
        staged.commit()


def cache_tree(root: Path):
    """Yield children without descending through directory symlinks."""
    if root.is_symlink():
        if root != CACHE_ROOT:
            return
        root = RESOLVED_CACHE_ROOT
    for parent, directories, files in walk(root, followlinks=False):
        for name in directories + files:
            yield Path(parent, name)


def is_preserved(path: Path, directories) -> bool:
    return any(path == directory or directory in path.parents for directory in directories)
