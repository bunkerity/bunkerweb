"""Recoverable, same-filesystem replacement of cached directories."""

from io import BytesIO
from base64 import b64decode, b64encode
from json import dumps, loads
from os import replace, walk
from pathlib import Path
from shutil import rmtree
from stat import S_IMODE
from tarfile import data_filter, open as tar_open
from tempfile import NamedTemporaryFile, mkdtemp

from common_utils import safe_tar_extractall

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


def write_atomic(target: Path, data: bytes) -> None:
    """Replace one file without exposing partial writes or following its symlink."""
    target = _check_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = S_IMODE(target.lstat().st_mode) if target.exists() else None
    for attempt in range(3):
        _check_path(target)
        with NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as tmp:
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

    The target is returned in the namespace the row carries, like restore_mtls_cache returns
    original_root / service. The container images link the installed cache root to /data/cache,
    so returning the resolved path would put ignored_dirs in one namespace and the sweep, which
    walks the installed plugin directory, in another: nothing would ever match and the sweep
    would delete the directory that was just extracted. Every writer re-checks the path.
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
    state = loads(journal.read_bytes()) if journal.exists() else None
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
            # A callable retains the helper's link-aware metadata checks while
            # Python's data filter also validates resolved symlink/hardlink targets.
            safe_tar_extractall(tar, staged.path, tar_filter=data_filter)
        staged.publish(companion_data)
        staged.commit()


def restore_mtls_cache(root: Path, rows) -> set:
    """Recover declared service transactions, then restore CA/optional CRL pairs."""
    original_root = root
    root = _check_path(root)
    rows = list(rows)
    pairs = {}
    for row in rows:
        if row["file_name"] not in ("ca.pem", "crl.pem"):
            continue
        service = row["service_id"] or ""
        target = checked_cache_path(root, service)
        if target.parent != root:
            raise ValueError(f"Invalid mTLS service cache directory: {target}")
        pairs.setdefault(service, {})[row["file_name"]] = row["data"]

    services = set(pairs)
    # Only transaction markers at this known plugin's immediate service level
    # establish authority when the last DB row has been deleted.
    for suffix in (".cache-journal", ".cache-backup"):
        for marker in root.glob(f".*{suffix}"):
            service = marker.name.removeprefix(".").removesuffix(suffix)
            if not service:
                # A stray ".cache-journal" resolves to the plugin root itself, which
                # checked_cache_path rejects; one such file would block every later restore.
                continue
            target = checked_cache_path(root, service)
            if target.parent != root:
                raise ValueError(f"Invalid mTLS transaction target: {target}")
            services.add(service)

    for service in services:
        recover_directory(root / service, keep_journal=True)
    for service in services:
        target = root / service
        pair = pairs.get(service, {})
        if pair and "ca.pem" not in pair:
            raise ValueError(f"mTLS cache for {service} has a CRL without its CA")
        if not pair and not target.exists():
            target.with_name(f".{target.name}.cache-journal").unlink(missing_ok=True)
            continue
        if not pair and not rows:
            # The rollback above is always safe; publishing an empty directory over the live pair
            # is not. With no row at all for this plugin the database says nothing -- a read that
            # returned nothing looks exactly like a deliberate deletion -- so the marker cannot
            # authorise wiping the CA the conf still needs. Deleting one service's rows while any
            # other service keeps its own still goes through the branch below. Same call as the
            # caller's "no cache row for this plugin, keep the files" safeguard, which the marker
            # would otherwise override. Drop the marker so the decision is not retaken every run.
            target.with_name(f".{target.name}.cache-journal").unlink(missing_ok=True)
            continue
        with StagedDirectory(target, keep_journal=True) as staged:
            for name, data in pair.items():
                if not isinstance(data, bytes):
                    raise ValueError(f"Missing mTLS cache data for {service}/{name}")
                write_atomic(staged.path / name, data)
                (staged.path / name).chmod(0o640)
            staged.path.chmod(0o750)
            staged.publish()
            staged.commit()
    preserved = set()
    for service in services:
        target = original_root / service
        preserved.add(target)
        preserved.update(transaction_markers(target))
    return preserved


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
