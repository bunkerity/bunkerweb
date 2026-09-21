from contextlib import suppress
from copy import copy
import fcntl
from gzip import GzipFile
from hashlib import new as new_hash
from ipaddress import ip_address
from inspect import signature
from io import BytesIO
import os
from os import (
    O_CREAT,
    O_RDWR,
    close as os_close,
    ftruncate,
    getenv,
    getpid,
    open as os_open,
    sched_getaffinity,
    sep,
    access,
    R_OK,
    cpu_count,
    write as os_write,
)
from os.path import join as path_join, normpath
from packaging.version import InvalidVersion, Version
from pathlib import Path
from platform import machine
from re import compile as re_compile
import tarfile
from tarfile import open as tar_open
from stat import S_ISDIR, S_ISREG
from threading import Lock
from time import monotonic, sleep
from typing import Dict, List, Optional, Tuple, Union, Any
from urllib.parse import urlsplit
from math import ceil, isfinite
import logging

PLUGIN_TAR_COMPRESS_LEVEL: int = 3
# Underscores are accepted because Docker/internal DNS commonly uses them in container names.
_HOSTNAME_LABEL_RX = re_compile(r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)$")
_DURATION_RX = re_compile(r"^(\d+(?:\.\d+)?)(ms|[smhdwMy])?$")
_DURATION_UNITS_MS = {"ms": 1, "s": 1000, "m": 60000, "h": 3600000, "d": 86400000, "w": 604800000, "M": 2592000000, "y": 31536000000}


def parse_duration(value: Any, default_unit: str = "s") -> Union[int, float]:
    """Return a duration expressed in ``default_unit``.

    Examples: ``parse_duration("2m") == 120`` and ``parse_duration("1500ms") == 1.5``.
    """
    if default_unit not in _DURATION_UNITS_MS:
        raise ValueError(f"Unknown duration unit: {default_unit}")
    match = _DURATION_RX.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f"Invalid duration: {value}")
    result = float(match.group(1)) * _DURATION_UNITS_MS[match.group(2) or default_unit] / _DURATION_UNITS_MS[default_unit]
    if not isfinite(result):
        raise ValueError(f"Duration out of range: {value}")
    return int(result) if result.is_integer() else result


def has_url_userinfo(value: Any) -> bool:
    """Return whether a hostname or URL contains a userinfo delimiter."""
    return isinstance(value, str) and "@" in value


def normalize_host(host: Any) -> str:
    """Return a canonical IP literal or IDNA DNS hostname."""
    if not isinstance(host, str) or not host or has_url_userinfo(host):
        raise ValueError("Invalid hostname")
    with suppress(ValueError):
        return str(ip_address(host))

    trailing_dot = host.endswith(".")
    try:
        hostname = host.removesuffix(".").encode("idna").decode("ascii").lower()
    except UnicodeError as e:
        raise ValueError("Invalid hostname") from e
    if not hostname or len(hostname) > 253 or not all(_HOSTNAME_LABEL_RX.fullmatch(label) for label in hostname.split(".")):
        raise ValueError("Invalid hostname")
    return f"{hostname}{'.' if trailing_dot else ''}"


def is_valid_host(host: Any) -> bool:
    """Validate a parsed IPv4/IPv6 literal or DNS-style hostname without scheme or port."""
    with suppress(ValueError):
        normalize_host(host)
        return True
    return False


def parse_host(value: Any) -> tuple[str, str, Optional[int]]:
    """Parse a hostname or HTTP(S) URL into scheme, canonical host and port."""
    if not isinstance(value, str) or not value or has_url_userinfo(value):
        raise ValueError("Invalid hostname")

    with suppress(ValueError):
        return "", normalize_host(value), None

    has_scheme = "://" in value
    try:
        parsed = urlsplit(value if has_scheme else f"//{value}")
        port = parsed.port
    except ValueError as e:
        raise ValueError(f"Invalid hostname: {e}") from e
    if has_scheme and parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Invalid hostname: only HTTP(S) URLs are supported")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Invalid hostname: paths, queries and fragments are not allowed")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid hostname: port must be between 1 and 65535")
    return parsed.scheme.lower(), normalize_host(parsed.hostname), port


def getenv_bool(name: str, default: str = "no") -> bool:
    return getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def handle_docker_secrets() -> Dict[str, str]:
    """Handle Docker secrets by reading from /run/secrets directory (Alpine only)"""
    secrets = {}

    # Only check for Docker secrets on Alpine Linux
    os_release_path = Path("/etc/os-release")
    if not os_release_path.is_file():
        return secrets

    try:
        os_release_content = os_release_path.read_text(encoding="utf-8")
        if "alpine" not in os_release_content.casefold():
            return secrets
    except Exception:
        return secrets

    secrets_dir = Path("/run/secrets")
    if secrets_dir.is_dir():
        for secret_file in secrets_dir.glob("*"):
            if secret_file.is_file():
                try:
                    secret_name = secret_file.name.upper()
                    secret_value = secret_file.read_text(encoding="utf-8").strip()
                    secrets[secret_name] = secret_value
                except Exception as e:
                    print(f"Warning: Failed to read Docker secret {secret_file.name}: {e}")

    return secrets


def dict_to_frozenset(d):
    if isinstance(d, list):
        return tuple(sorted(d))
    elif isinstance(d, dict):
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


def get_version() -> str:
    return Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text(encoding="utf-8").strip()


def get_integration() -> str:
    try:
        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if getenv("KUBERNETES_MODE", "no").lower() == "yes":
            return "Kubernetes"
        elif getenv("SWARM_MODE", "no").lower() == "yes":
            return "Swarm"
        elif getenv("AUTOCONF_MODE", "no").lower() == "yes":
            return "Autoconf"
        elif integration_path.is_file():
            return integration_path.read_text(encoding="utf-8").strip().title()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
            return "Docker"

        return "Linux"
    except:
        return "Unknown"


def get_os_info() -> Dict[str, str]:
    os_data = {
        "name": "Linux",
        "version": "Unknown",
        "version_id": "Unknown",
        "version_codename": "Unknown",
        "id": "Unknown",
        "arch": machine(),
    }

    os_release = Path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text().splitlines():
            if "=" not in line or line.split("=")[0].strip().lower() not in os_data:
                continue
            os_data[line.split("=")[0].lower()] = line.split("=")[1].strip('"')

    return os_data


def _cgroup_cpu_limit() -> Optional[int]:
    with suppress(Exception):
        cpu_max = Path("/sys/fs/cgroup/cpu.max").read_text().strip()
        quota, period = cpu_max.split()
        if quota != "max":
            quota_value = int(quota)
            period_value = int(period)
            if quota_value > 0 and period_value > 0:
                return max(1, ceil(quota_value / period_value))

    with suppress(Exception):
        quota_value = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text().strip())
        period_value = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text().strip())
        if quota_value > 0 and period_value > 0:
            return max(1, ceil(quota_value / period_value))

    return None


def effective_cpu_count() -> int:
    candidates = [cpu_count() or 1]

    with suppress(Exception):
        candidates.append(len(sched_getaffinity(0)))

    cgroup_limit = _cgroup_cpu_limit()
    if cgroup_limit:
        candidates.append(cgroup_limit)

    return max(1, min(candidates))


def file_hash(file: Union[str, Path], *, algorithm: str = "sha512") -> str:
    _hash = new_hash(algorithm)
    if not isinstance(file, Path):
        file = Path(file)

    with file.open("rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            _hash.update(data)
    return _hash.hexdigest()


def bytes_hash(bio: Union[str, bytes, BytesIO], *, algorithm: str = "sha512") -> str:
    if isinstance(bio, str):
        bio = BytesIO(bio.encode("utf-8"))
    elif isinstance(bio, bytes):
        bio = BytesIO(bio)

    assert isinstance(bio, BytesIO)

    _hash = new_hash(algorithm)
    while True:
        data = bio.read(1024)
        if not data:
            break
        _hash.update(data)
    bio.seek(0, 0)
    return _hash.hexdigest()


# -----------------------
# Safe tar helper utilities
# -----------------------

_EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
}

_EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}
_EXCLUDED_FILE_NAMES = {".DS_Store"}


def plugin_tar_exclude(path: Union[str, Path]) -> bool:
    """Return True if a path should be excluded from plugin tar archives.

    Excludes cache/hidden directories, compiled files, platform junk, and unreadable files.
    """
    p = Path(path)
    try:
        if any(part in _EXCLUDED_DIR_NAMES for part in p.parts):
            return True
        if p.suffix in _EXCLUDED_FILE_SUFFIXES:
            return True
        if p.name in _EXCLUDED_FILE_NAMES:
            return True
        if p.is_file() and not access(p.as_posix(), R_OK):
            return True
    except Exception:
        # Be conservative if checks fail
        return True
    return False


def plugin_tar_filter(tarinfo):
    """Tar filter for plugin archives to drop unwanted entries."""
    try:
        name = getattr(tarinfo, "name", "")
        p = Path(name)
        if any(part in _EXCLUDED_DIR_NAMES for part in p.parts):
            return None
        if p.suffix in _EXCLUDED_FILE_SUFFIXES:
            return None
        if p.name in _EXCLUDED_FILE_NAMES:
            return None
        tarinfo.mtime = 0
        tarinfo.uid = 0
        tarinfo.gid = 0
        tarinfo.uname = "root"
        tarinfo.gname = "root"
        return tarinfo
    except Exception:
        return None


def add_dir_to_tar_safely(tar: Any, dir_path: Union[str, Path], arc_root: Optional[str] = None):
    """Recursively add a directory to an open TarFile, safely.

    - Skips excluded/unreadable files and directories via plugin_tar_exclude
    - Applies plugin_tar_filter on files/dirs

    Args:
        tar: an open TarFile in write mode
        dir_path: root directory to add
        arc_root: name of the directory inside the archive (defaults to basename)
    """
    d = Path(dir_path)
    if not d.exists():
        return
    if arc_root is None:
        arc_root = d.name

    # Ensure the root directory entry exists (non-recursive)
    with suppress(Exception):
        if not plugin_tar_exclude(d):
            tar.add(d.as_posix(), arcname=arc_root, recursive=False, filter=plugin_tar_filter)

    for p in sorted(d.rglob("*")):
        if plugin_tar_exclude(p):
            continue
        arcname = f"{arc_root}/{p.relative_to(d).as_posix()}"
        with suppress(Exception):
            if p.is_dir():
                tar.add(p.as_posix(), arcname=arcname, recursive=False, filter=plugin_tar_filter)
            elif p.is_file() and access(p.as_posix(), R_OK):
                tar.add(p.as_posix(), arcname=arcname, recursive=False, filter=plugin_tar_filter)
            # unreadable files are ignored silently


def create_plugin_tar_gz(dir_path: Union[str, Path], arc_root: Optional[str] = None) -> BytesIO:
    """Create a deterministic gzip-compressed tar archive of a plugin directory.

    Uses a fixed gzip mtime of 0 so that the same directory content always
    produces identical bytes (and therefore the same SHA-256 checksum).
    The result is a seeked-to-zero BytesIO ready for hashing or reading.
    """
    d = Path(dir_path)
    if arc_root is None:
        arc_root = d.name

    # 1. Build an uncompressed tar in memory
    with BytesIO() as raw:
        with tar_open(fileobj=raw, mode="w") as tar:
            add_dir_to_tar_safely(tar, d, arc_root=arc_root)
        raw_bytes = raw.getvalue()

    # 2. Compress with a deterministic gzip header (mtime=0)
    result = BytesIO()
    with GzipFile(fileobj=result, mode="wb", compresslevel=PLUGIN_TAR_COMPRESS_LEVEL, mtime=0) as gz:
        gz.write(raw_bytes)
    result.seek(0)
    return result


def _validate_tar_members(members, *, links="none"):
    """Pre-validate tar members before extraction (defense-in-depth against CVE-2025-4517).

    Checks archive metadata only — no disk access — so PATH_MAX symlink chain attacks are impossible.
    When links is "none", all symlinks/hardlinks are rejected. When links is "contained",
    symlinks and hardlinks are permitted when their targets remain inside the destination.
    """
    for member in members:
        # Block absolute paths
        if member.name.startswith("/"):
            raise ValueError(f"Tar member {member.name!r} has absolute path")
        # Block path traversal in member name
        if ".." in Path(member.name).parts:
            raise ValueError(f"Tar member {member.name!r} contains '..'")
        # Block device files and pipes
        if member.isdev() or member.isfifo():
            raise ValueError(f"Tar member {member.name!r} is a device or pipe")
        # Check symlinks/hardlinks
        if member.issym() or member.islnk():
            if links == "none":
                raise ValueError(f"Tar member {member.name!r} is a symlink/hardlink (not permitted)")
            if Path(member.linkname).is_absolute():
                raise ValueError(f"Tar member {member.name!r} links to absolute path {member.linkname!r}")
            # Normalize to collapse valid .. segments, then check if any remain (= escaping)
            link_parent = Path(member.name).parent if member.issym() else Path()
            normalized = normpath(path_join(str(link_parent), member.linkname))
            if ".." in Path(normalized).parts:
                raise ValueError(f"Tar member {member.name!r} links outside target directory")


def _supports_tar_filter(tar) -> bool:
    try:
        return "filter" in signature(tar.extract).parameters
    except (TypeError, ValueError):
        return False


def _is_contained(candidate, destination):
    return os.path.commonpath([candidate, destination]) == destination


def _has_symlinked_parent(parent, path):
    relative = os.path.relpath(parent, path)
    if relative == os.curdir:
        return False
    current = path
    for part in Path(relative).parts:
        current = os.path.join(current, part)
        if os.path.lexists(current) and os.path.islink(current):
            return True
    return False


def _resolve_path(path):
    """Resolve links component-by-component so a link followed by '..' cannot hide an escape."""
    path = os.fspath(path)
    if not os.path.isabs(path):
        path = os.path.join(Path.cwd(), path)
    pending = list(Path(path).parts)
    resolved = []
    link_count = 0
    while pending:
        part = pending.pop(0)
        if part in (os.curdir, os.sep):
            if part == os.sep:
                resolved = [os.sep]
            continue
        if part == os.pardir:
            if len(resolved) > 1:
                resolved.pop()
            continue
        candidate = os.path.join(*resolved, part)
        if os.path.islink(candidate):
            link_count += 1
            if link_count > 40:
                raise OSError("too many symbolic links")
            target = os.readlink(candidate)
            if os.path.isabs(target):
                resolved = [os.sep]
            pending = list(Path(target).parts) + pending
            continue
        resolved.append(part)
    return os.path.join(*resolved) if resolved != [os.sep] else os.sep


def _verify_tar_tree(path, links, destination, members):
    relative = "."

    try:
        for member in members:
            relative = member.name
            entry = os.path.join(path, member.name)
            mode = os.lstat(entry).st_mode
            if os.path.islink(entry):
                if links == "none":
                    raise ValueError(f"Tar member {relative!r} is a symlink (not permitted)")
                target = os.path.join(path, os.path.dirname(member.name), member.linkname)
                if not _is_contained(_resolve_path(target), destination):
                    raise ValueError(f"Tar member {relative!r} links outside target directory")
            elif member.islnk():
                target = os.path.join(path, member.linkname)
                if not _is_contained(_resolve_path(target), destination):
                    raise ValueError(f"Tar member {relative!r} links outside target directory")
            elif not (S_ISDIR(mode) or S_ISREG(mode)):
                raise ValueError(f"Tar member {relative!r} is an unexpected entry type")
    except (OSError, ValueError) as error:
        if isinstance(error, ValueError) and str(error).startswith("Tar member "):
            raise
        raise ValueError(f"Tar member {relative!r} could not be verified: {error}") from error


def safe_tar_extractall(tar, path, *, links="none", **kwargs):
    """Extract a tar archive with runtime-independent path and link containment checks."""
    if links not in ("none", "contained"):
        raise ValueError(f"Unsupported links policy: {links!r}")
    if "tar_filter" in kwargs:
        raise TypeError("safe_tar_extractall() got an unexpected keyword argument 'tar_filter'")

    members = kwargs.pop("members", None)
    numeric_owner = kwargs.pop("numeric_owner", False)
    members = list(tar.getmembers() if members is None else members)
    if kwargs:
        name = next(iter(kwargs))
        raise TypeError(f"safe_tar_extractall() got an unexpected keyword argument {name!r}")
    _validate_tar_members(members, links=links)

    destination = os.path.realpath(path)
    supports_filter = _supports_tar_filter(tar)
    native_filter = getattr(tarfile, "data_filter", None) if supports_filter else None
    extract_parameters = signature(tar.extract).parameters
    extract_kwargs = {}
    if "numeric_owner" in extract_parameters:
        extract_kwargs["numeric_owner"] = numeric_owner
    if native_filter is not None:
        extract_kwargs["filter"] = native_filter

    directories = []
    for member in members:
        try:
            member_path = os.path.join(path, member.name)
            member_parent = os.path.join(path, os.path.dirname(member.name))
            if not _is_contained(os.path.realpath(member_parent), destination):
                raise ValueError(f"Tar member {member.name!r} parent escapes target directory")
            if _has_symlinked_parent(member_parent, path):
                raise ValueError(f"Tar member {member.name!r} writes through a symlinked parent")
            if os.path.lexists(member_path) and os.path.islink(member_path):
                raise ValueError(f"Tar member {member.name!r} replaces an existing symlink")
            if member.issym() and not _is_contained(os.path.realpath(os.path.join(path, os.path.dirname(member.name), member.linkname)), destination):
                raise ValueError(f"Tar member {member.name!r} links outside target directory")
            if member.islnk() and not _is_contained(os.path.realpath(os.path.join(path, member.linkname)), destination):
                raise ValueError(f"Tar member {member.name!r} links outside target directory")
            extract_member = member
            if member.isdir():
                extract_member = copy(member)
                extract_member.mode = 0o700
                directories.append((member, member_path))
            tar.extract(extract_member, path, **extract_kwargs)
        except (OSError, ValueError, tarfile.TarError, KeyError) as error:
            if isinstance(error, ValueError) and str(error).startswith("Tar member "):
                raise
            raise ValueError(f"Tar member {member.name!r} could not be extracted: {error}") from error

    _verify_tar_tree(path, links, destination, members)
    for member, member_path in sorted(directories, key=lambda item: item[0].name, reverse=True):
        try:
            try:
                is_directory = S_ISDIR(os.lstat(member_path).st_mode)
            except FileNotFoundError:
                continue
            if not is_directory:
                continue
            # Keep the archive's directory mode (0o700 on the certbot key directories) minus
            # setuid/setgid/sticky and group/other write: data_filter drops directory modes and
            # the runtimes without it would apply the raw mode.
            directory_mode = member.mode & 0o755 if member.mode is not None else None
            if native_filter is not None:
                attributes = native_filter(member, path)
                if attributes is None:
                    continue
                if attributes.mode is None and directory_mode is not None:
                    attributes = attributes.replace(mode=directory_mode, deep=False)
            else:
                attributes = copy(member)
                attributes.mode = directory_mode
            tar.chown(attributes, member_path, numeric_owner)
            tar.utime(attributes, member_path)
            tar.chmod(attributes, member_path)
        except (OSError, ValueError, tarfile.TarError, KeyError) as error:
            if isinstance(error, ValueError) and str(error).startswith("Tar member "):
                raise
            raise ValueError(f"Tar member {member.name!r} could not be finalized: {error}") from error


def safe_zip_extractall(zf, path):
    """Extract a zip archive safely, rejecting members with absolute paths or path traversal."""
    dest = Path(path).resolve()
    for member in zf.namelist():
        member_path = (dest / member).resolve()
        # Path.is_relative_to() was added in Python 3.9; fall back to relative_to()
        # for older interpreters so this helper still raises on traversal attempts.
        try:
            contained = member_path.is_relative_to(dest)
        except AttributeError:
            try:
                member_path.relative_to(dest)
                contained = True
            except ValueError:
                contained = False
        if not contained:
            raise ValueError(f"Zip member {member!r} would escape target directory")
    zf.extractall(path)


class DatabaseLockBusy(Exception):
    """Raised by acquire_db_lock() when the lock could not be taken before the deadline."""


def acquire_db_lock(path: Path, timeout: float = 30.0) -> int:
    """Acquire a real mutual-exclusion lock on `path` using fcntl.flock(LOCK_EX).

    Assumption: the lock file lives on a single local filesystem shared by the
    scheduler process and the bwcli commands (docker exec into the scheduler
    container, or the same Linux host), and there is exactly one scheduler per
    database, so a local-filesystem flock is adequate (it would NOT be safe
    across NFS or between hosts).

    The file is opened (never truncated, never unlinked) and LOCK_EX|LOCK_NB is
    retried in a 1s loop until `timeout` seconds (monotonic clock) elapse. On
    success the holder's pid is written into the file (informational only) and
    the open file descriptor is returned; the caller must pass it to
    release_db_lock() when done. On timeout DatabaseLockBusy is raised and the
    existing holder's lock is left untouched (no stealing).

    If a holder process dies, the kernel releases its flock automatically, so
    no dead-owner reaper is needed here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os_open(str(path), O_RDWR | O_CREAT, 0o600)
    deadline = monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if monotonic() >= deadline:
                holder_pid = ""
                with suppress(OSError):
                    holder_pid = path.read_text().strip()
                os_close(fd)
                if holder_pid:
                    raise DatabaseLockBusy(f"database is locked by pid {holder_pid}, try again later")
                raise DatabaseLockBusy("database is locked, try again later")
            sleep(1)

    with suppress(OSError):
        ftruncate(fd, 0)
        os_write(fd, str(getpid()).encode())

    return fd


def release_db_lock(fd: int) -> None:
    """Release a lock handle obtained via acquire_db_lock().

    Ownership-aware: unlocks and closes only the given fd. flock() locks are
    scoped to the open file description behind that fd, so releasing (or
    double-releasing) one fd can never touch another owner's lock on the same
    path, and never unlinks the lock file.
    """
    with suppress(OSError):
        fcntl.flock(fd, fcntl.LOCK_UN)
    with suppress(OSError):
        os_close(fd)


def normalize_bunkerweb_version(version: str) -> str:
    """Normalize BunkerWeb version strings for semantic comparison.

    Converts Debian-style pre-release versions such as ``1.6.9~rc2`` to
    ``1.6.9-rc2`` so they can be parsed by ``packaging.version.Version``.
    """
    return version.strip().lower().removeprefix("v").replace("~", "-")


def is_newer_version_available(current_version: str, latest_version: str) -> bool:
    """Return True when the latest version is newer than the current one.

    Returns False when semantic parsing fails, since a false negative (missing
    an update notification) is safer than a false positive.
    """
    current_normalized = normalize_bunkerweb_version(current_version)
    latest_normalized = normalize_bunkerweb_version(latest_version)

    try:
        return Version(current_normalized) < Version(latest_normalized)
    except InvalidVersion:
        return False


_REDIS_CLIENT_LOCK = Lock()
# Single-entry, process-wide memo: (cache_key, client_or_None, negative_window_deadline).
# A configuration change yields a different key and therefore a new client, so there is no
# separate invalidation path. The superseded client is never closed: the Web UI hands the
# very same object to flask-session as app.config["SESSION_REDIS"], and closing it would
# break every live session in the worker. Dropping the reference is enough, the pool is
# garbage collected once nothing uses it.
_REDIS_CLIENT_ENTRY: Optional[Tuple[tuple, Any, float]] = None

# How long a failed connection is remembered before another connect is attempted.
# REDIS_TIMEOUT feeds both socket_timeout and socket_connect_timeout (default 1000 ms), so
# without a negative window every single request against a down Redis pays a full timeout.
REDIS_NEGATIVE_CACHE_SECONDS = 10.0


def shared_redis_pool_size() -> int:
    """Upper bound on connections in the process-wide Redis pool.

    Deliberately NOT derived from REDIS_KEEPALIVE_POOL: that setting sizes the per-NGINX-worker
    keepalive pool of the OpenResty Lua client and means nothing here. It was only safe as a
    Python max_connections while every call owned a private pool.

    Now that one client is shared, the cap has to cover everything in the process that can
    talk to Redis at once: the gunicorn gthread request threads (MAX_THREADS, defaulting to
    MAX_WORKERS * 2, src/ui/utils/gunicorn.conf.py) plus the two 4-worker executors in
    src/ui/app/dependencies.py. redis-py *raises* MaxConnectionsError rather than blocking
    once the pool is exhausted, so this is a hard ceiling, not a target. Connections are
    created lazily, so a generous cap costs nothing while idle.
    """
    try:
        workers = int(getenv("MAX_WORKERS") or max(effective_cpu_count() - 1, 1))
    except ValueError:
        workers = 1
    try:
        threads = int(getenv("MAX_THREADS") or workers * 2)
    except ValueError:
        threads = workers * 2

    # + 8 for CONFIG_TASKS_EXECUTOR and PAGE_TASKS_EXECUTOR, doubled for short overlaps
    # (a thread holding a connection while another is checked out), floored at 32.
    return max(32, (max(threads, 1) + 8) * 2)


def get_redis_client(
    use_redis: bool = False,
    redis_host: Optional[str] = None,
    redis_port: Union[str, int] = "6379",
    redis_db: Union[str, int] = "0",
    redis_timeout: Union[str, float] = "1000.0",
    redis_keepalive_pool: Union[str, int] = "10",
    redis_ssl: bool = False,
    redis_ssl_verify: bool = True,
    redis_username: Optional[str] = None,
    redis_password: Optional[str] = None,
    redis_sentinel_hosts: Union[List[List[str]], List[tuple], str] = [],
    redis_sentinel_username: Optional[str] = None,
    redis_sentinel_password: Optional[str] = None,
    redis_sentinel_master: str = "",
    logger: Optional[logging.Logger] = None,
) -> Any:
    """
    Get a Redis client using provided configuration parameters.

    Args:
        use_redis: Whether to use Redis or not
        redis_host: Redis host address
        redis_port: Redis port number
        redis_db: Redis database number
        redis_timeout: Connection timeout in milliseconds
        redis_keepalive_pool: Maximum connections in pool
        redis_ssl: Whether to use SSL for connection
        redis_ssl_verify: Whether to verify the Redis server certificate (REDIS_SSL_VERIFY)
        redis_username: Redis username for authentication
        redis_password: Redis password for authentication
        redis_sentinel_hosts: List of Redis Sentinel hosts
        redis_sentinel_username: Redis Sentinel username
        redis_sentinel_password: Redis Sentinel password
        redis_sentinel_master: Redis Sentinel master name
        logger: Logger instance for logging errors

    Returns:
        Redis client instance or None if connection fails
    """
    global _REDIS_CLIENT_ENTRY

    if not use_redis:
        return None

    try:
        from redis import StrictRedis, Sentinel
    except ImportError:
        if logger:
            logger.error("Redis package is not installed")
        return None

    if not redis_host and not redis_sentinel_hosts:
        if logger:
            logger.error("Neither redis_host nor redis_sentinel_hosts is provided")
        return None

    # Convert string parameters to appropriate types
    try:
        if isinstance(redis_port, str):
            redis_port = int(redis_port)

        if isinstance(redis_db, str):
            redis_db = int(redis_db)

        if isinstance(redis_timeout, str):
            redis_timeout = float(parse_duration(redis_timeout, "ms"))

        if isinstance(redis_keepalive_pool, str):
            redis_keepalive_pool = int(redis_keepalive_pool)
    except ValueError as e:
        if logger:
            logger.error(f"Error converting redis parameters: {e}")
            logger.error("Using defaults: redis_port=6379, redis_db=0, redis_timeout=1000.0, redis_keepalive_pool=10")
        redis_port = 6379
        redis_db = 0
        redis_timeout = 1000.0
        redis_keepalive_pool = 10

    # Process sentinel hosts if provided as string
    if isinstance(redis_sentinel_hosts, str):
        redis_sentinel_hosts = [tuple(host.split(":", 1)) if ":" in host else (host, "26379") for host in redis_sentinel_hosts.split() if host]

    # Every connection parameter except the logger, so a configuration change simply
    # produces a different key.
    cache_key = (
        redis_host,
        redis_port,
        redis_db,
        redis_timeout,
        redis_ssl,
        redis_ssl_verify,
        redis_username,
        redis_password,
        tuple(tuple(host) for host in redis_sentinel_hosts),
        redis_sentinel_username,
        redis_sentinel_password,
        redis_sentinel_master,
    )

    entry = _REDIS_CLIENT_ENTRY
    if entry is not None and entry[0] == cache_key:
        if entry[1] is not None:
            # No ping on a cache hit: it never proved anything about the next command, and
            # every Redis branch in the Web UI already falls back to the instance HTTP APIs.
            return entry[1]
        if monotonic() < entry[2]:
            return None

    # ssl_cert_reqs is only meaningful on a TLS connection, and the non-SSL Sentinel
    # connection class does not accept it at all.
    ssl_kwargs = {"ssl_cert_reqs": "required" if redis_ssl_verify else "none"} if redis_ssl else {}

    redis_client = None

    try:
        # Connect via Sentinel if sentinel hosts are provided
        if redis_sentinel_hosts:
            if logger:
                logger.info(f"Connecting to Redis Sentinel cluster: {redis_sentinel_hosts}")

            sentinel = Sentinel(
                redis_sentinel_hosts,
                username=redis_sentinel_username,
                password=redis_sentinel_password,
                ssl=redis_ssl,
                socket_timeout=redis_timeout / 1000,
                socket_connect_timeout=redis_timeout / 1000,
                socket_keepalive=True,
                max_connections=shared_redis_pool_size(),
                **ssl_kwargs,
            )

            # Test the connection. No inner handler: a Sentinel failure must reach the outer
            # except below, which is what arms the negative window. Returning early here left
            # every request paying a full discover_master timeout against a down Sentinel.
            sentinel.discover_master(redis_sentinel_master)

            # Get master connection
            redis_client = sentinel.master_for(
                redis_sentinel_master,
                db=redis_db,
                username=redis_username,
                password=redis_password,
            )

        # Direct connection to Redis
        else:
            if not redis_host:
                if logger:
                    logger.error("redis_host is required when not using sentinel")
                return None
            if logger:
                logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")

            redis_client = StrictRedis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                username=redis_username,
                password=redis_password,
                socket_timeout=redis_timeout / 1000,
                socket_connect_timeout=redis_timeout / 1000,
                socket_keepalive=True,
                max_connections=shared_redis_pool_size(),
                ssl=redis_ssl,
                **ssl_kwargs,
            )

        # Test the connection once, when the client is built.
        redis_client.ping()
        if logger:
            logger.info("Successfully connected to Redis")

        # Built outside the lock, published under it: holding a lock across a connect would
        # serialise every thread in the worker behind one slow handshake.
        with _REDIS_CLIENT_LOCK:
            entry = _REDIS_CLIENT_ENTRY
            if entry is not None and entry[0] == cache_key and entry[1] is not None:
                # Another thread won the race; drop ours (never close it) and share theirs.
                return entry[1]
            _REDIS_CLIENT_ENTRY = (cache_key, redis_client, 0.0)

        return redis_client

    except Exception as e:
        if logger:
            logger.error(f"Failed to connect to Redis: {e}")
        with _REDIS_CLIENT_LOCK:
            entry = _REDIS_CLIENT_ENTRY
            if entry is None or entry[0] != cache_key or entry[1] is None:
                _REDIS_CLIENT_ENTRY = (cache_key, None, monotonic() + REDIS_NEGATIVE_CACHE_SECONDS)
        return None
