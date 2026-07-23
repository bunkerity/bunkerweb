from contextlib import suppress
from gzip import GzipFile
from hashlib import new as new_hash
from ipaddress import ip_address
from io import BytesIO
from os import getenv, sched_getaffinity, sep, access, R_OK, cpu_count
from os.path import join as path_join, normpath
from packaging.version import InvalidVersion, Version
from pathlib import Path
from platform import machine
from re import compile as re_compile
from tarfile import open as tar_open
from typing import Dict, List, Optional, Tuple, Union, Any
from urllib.parse import urlsplit
from math import ceil
import logging

PLUGIN_TAR_COMPRESS_LEVEL: int = 3
# Underscores are accepted because Docker/internal DNS commonly uses them in container names.
_HOSTNAME_LABEL_RX = re_compile(r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)$")


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
    """Handle Docker secrets by reading from the /run/secrets directory when it exists."""
    secrets = {}

    # Docker/Swarm secrets are mounted at /run/secrets regardless of the base distro.
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


# Canonical truthy/falsy tokens for "check" type settings. Inputs are trimmed and
# lowercased before lookup. Callers apply this ONLY to type=="check" settings so the
# stored and consumed value is always the canonical "yes"/"no" the rest of the stack
# (Lua `== "yes"`, Jinja conditionals, jobs) already expects.
_CHECK_TRUE_TOKENS = frozenset(("yes", "y", "true", "t", "on", "1", "enable", "enabled"))
_CHECK_FALSE_TOKENS = frozenset(("no", "n", "false", "f", "off", "0", "disable", "disabled"))


def normalize_check_value(value: Any) -> Any:
    """Canonicalize a truthy/falsy string to "yes"/"no" for check-type settings.

    Matching is case-insensitive and ignores surrounding whitespace. Known tokens map
    to "yes"/"no"; any other value (including non-strings) is returned unchanged so the
    setting's ^(yes|no)$ regex still rejects it. Idempotent on canonical input.
    """
    if not isinstance(value, str):
        return value
    token = value.strip().lower()
    if token in _CHECK_TRUE_TOKENS:
        return "yes"
    if token in _CHECK_FALSE_TOKENS:
        return "no"
    return value


def normalize_list_value(value: Any, separator: str = " ") -> Any:
    """Canonicalize a multivalue/multiselect string for storage.

    Split on ``separator``, strip each item, drop empty items, and rejoin with a single
    ``separator``. Non-strings (and an empty separator) are returned unchanged. This only
    cleans the stored form — it mirrors what list consumers already compute (the schema
    regexes already tolerate surrounding spaces, and consumers strip per item), so it
    changes no acceptance decision (e.g. " 10.0.0.1  10.0.0.2 " -> "10.0.0.1 10.0.0.2").
    Idempotent on canonical input.
    """
    if not isinstance(value, str) or not separator:
        return value
    items = [item.strip() for item in value.split(separator)]
    return separator.join(item for item in items if item)


# Setting types where leading/trailing whitespace can be semantically meaningful and
# therefore MUST NOT be trimmed at ingestion: free-form/regex text, file bodies, and
# secrets. Every other scalar type (number, select, check, size, duration, lists) is
# safe to trim — check/size/duration/list helpers already strip internally, so the
# net-new effect is on number/select (and any future scalar type).
NO_TRIM_TYPES = frozenset(("password", "file", "text"))


def trim_scalar_value(setting_type: Any, value: Any) -> Any:
    """Strip surrounding whitespace from a scalar setting value before type canonicalization.

    No-op for non-strings, for the NO_TRIM_TYPES exclusion set, and for an unknown/empty type
    (so a value whose schema wasn't resolved is never wrongly trimmed). Idempotent:
    ``trim(trim(v)) == trim(v)``.
    """
    if isinstance(value, str) and setting_type and setting_type not in NO_TRIM_TYPES:
        return value.strip()
    return value


def normalize_select_value(value: Any, options, *, multi: bool = False, separator: str = " ", case_insensitive: bool = False) -> Any:
    """Casefold-map a select/multiselect value to its declared option casing (A3, opt-in).

    No-op unless ``case_insensitive`` is set and ``value`` is a string and ``options`` is
    non-empty. ``options`` is the flat list of canonical option strings (the stored values).
    A token matching an option case-insensitively is rewritten to that option's casing; a
    token with no match is returned unchanged so the schema regex still rejects it. For
    ``multi`` the value is split on ``separator`` (empty separator -> returned unchanged,
    can't tokenize), each item mapped, then rejoined. Expects ``multi`` input already cleaned
    by ``normalize_list_value`` (trimmed items). Idempotent on canonical input.
    """
    if not case_insensitive or not isinstance(value, str) or not options:
        return value
    canon = {}
    for opt in options:
        key = str(opt).casefold()
        if key not in canon:  # first declaration wins on a casefold collision
            canon[key] = opt
    if not multi:
        return canon.get(value.casefold(), value)
    if not separator:
        return value
    return separator.join(canon.get(item.casefold(), item) for item in value.split(separator))


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
        elif Path(sep, ".dockerenv").is_file() or (os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8")):
            # /.dockerenv exists in every Docker container regardless of base distro (Alpine match
            # kept for backward compatibility); os-release no longer says "Alpine" on the Debian images.
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


# Allowlisted, root-level icon files a plugin may ship inside its own archive, in
# resolution-priority order. When one is present it is recorded in Plugins.icon as a
# "@file/<name>" marker and served (never inlined) via GET /plugins/{id}/icon. Fixed names
# + root-only membership means there is no path-traversal surface to serve them.
PLUGIN_ICON_FILES = ("icon.svg", "icon.png", "logo.svg", "logo.png")
_PLUGIN_ICON_CONTENT_TYPES = {".svg": "image/svg+xml", ".png": "image/png"}


def plugin_icon_content_type(name: str) -> str:
    """Content-Type for an allowlisted plugin icon file name (defaults to octet-stream)."""
    return _PLUGIN_ICON_CONTENT_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


def _root_level_icon_name(member_name: str, allowed: set) -> Optional[str]:
    """Return the allowlisted basename when ``member_name`` is a root-level icon inside a
    plugin archive (at the archive root, or directly under its single top-level dir), else
    None. Deeper paths (e.g. ``<id>/ui/icon.svg``) are intentionally not matched."""
    parts = member_name.strip("/").split("/")
    if 1 <= len(parts) <= 2 and parts[-1] in allowed:
        return parts[-1]
    return None


def detect_plugin_icon(data: Union[bytes, bytearray, BytesIO]) -> Optional[str]:
    """First allowlisted root-level icon file name shipped in a plugin ``tar.gz`` blob, in
    PLUGIN_ICON_FILES priority order (icon.svg > icon.png > logo.svg > logo.png), or None.
    Deterministic; swallows any archive error and returns None (bad/foreign blob -> no icon)."""
    if isinstance(data, (bytes, bytearray)):
        data = BytesIO(bytes(data))
    allowed = set(PLUGIN_ICON_FILES)
    found = set()
    try:
        data.seek(0)
        with tar_open(fileobj=data, mode="r:*") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name = _root_level_icon_name(member.name, allowed)
                if name:
                    found.add(name)
    except Exception:
        return None
    for candidate in PLUGIN_ICON_FILES:
        if candidate in found:
            return candidate
    return None


def read_plugin_icon(data: Union[bytes, bytearray, BytesIO], name: str, *, max_bytes: int = 512 * 1024) -> Optional[Tuple[Optional[bytes], bool]]:
    """Extract allowlisted root-level file ``name`` from a plugin ``tar.gz`` blob.

    Returns:
      - ``None`` when ``name`` is not allowlisted or not present in the archive (caller -> 404);
      - ``(None, True)`` when the stored file exceeds ``max_bytes`` (caller -> 413) — at most
        ``max_bytes + 1`` bytes are ever read, so a huge member never loads fully into memory;
      - ``(payload, False)`` with the file bytes otherwise.
    """
    if name not in PLUGIN_ICON_FILES:
        return None
    if isinstance(data, (bytes, bytearray)):
        data = BytesIO(bytes(data))
    allowed = {name}
    try:
        data.seek(0)
        with tar_open(fileobj=data, mode="r:*") as tar:
            for member in tar.getmembers():
                if not member.isfile() or _root_level_icon_name(member.name, allowed) != name:
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    return None
                chunk = extracted.read(max_bytes + 1)
                if len(chunk) > max_bytes:
                    return None, True
                return chunk, False
    except Exception:
        return None
    return None


def read_local_plugin_icon(dir_path: Union[str, Path], name: str, *, max_bytes: int = 512 * 1024) -> Optional[Tuple[Optional[bytes], bool]]:
    """Read allowlisted icon file ``name`` directly from a plugin directory on disk.

    Core plugins ship their icon in-dir (``<core>/<id>/icon.svg``) and carry no data blob, so the
    icon endpoint reads them straight off the filesystem. Same return contract as
    ``read_plugin_icon``: ``None`` (absent / not allowlisted / read error) -> 404,
    ``(None, True)`` (over ``max_bytes``) -> 413, ``(payload, False)`` -> the bytes. ``name`` is
    constrained to the fixed 4-name allowlist (no slashes), so there is no path-traversal surface."""
    if name not in PLUGIN_ICON_FILES:
        return None
    path = Path(dir_path) / name
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > max_bytes:
            return None, True
        return path.read_bytes(), False
    except OSError:
        return None


def detect_local_plugin_icon(dir_path: Union[str, Path]) -> Optional[str]:
    """First allowlisted icon file present as a regular file directly in ``dir_path``, in
    PLUGIN_ICON_FILES priority order (icon.svg > icon.png > logo.svg > logo.png), or None.
    On-disk sibling of ``detect_plugin_icon`` for core plugins, which ship their icon in their
    own directory (``<core>/<id>/icon.svg``) instead of an archive blob."""
    base = Path(dir_path)
    for candidate in PLUGIN_ICON_FILES:
        if (base / candidate).is_file():
            return candidate
    return None


def resolve_plugin_icon(data: Optional[Union[bytes, bytearray, BytesIO]], icon_field: Any, *, dir_path: Optional[Union[str, Path]] = None) -> Optional[str]:
    """Effective ``Plugins.icon`` value for a plugin, applying the resolution order:

      1. an allowlisted icon file shipped in the archive ``data`` blob -> ``@file/<name>``
         (external/ui/pro plugins, whose files live in the tarball);
      2. no ``data`` blob and a ``dir_path`` was given (the core-plugin path: icons ship in-dir,
         auto-detected from the plugin's own directory):
           a. the plugin.json ``icon`` names an allowlisted file that actually exists in
              ``dir_path`` -> ``@file/<field>`` (explicit override, honored only when real);
           b. else the first allowlisted file found in ``dir_path``
              (``detect_local_plugin_icon``) -> ``@file/<detected>``;
           c. else the ``icon`` string verbatim (a ``*.svg`` static-asset name or a boxicon
              class) or None;
      3. no ``data`` blob and NO ``dir_path`` (back-compat for callers without a path): the
         plugin.json ``icon`` names an allowlisted file -> ``@file/<field>``;
      4. any other plugin.json ``icon`` string -> returned verbatim. This also covers a ``data``
         blob that was checked and did NOT contain the icon file its own plugin.json names: the
         string is not promoted to an ``@file/`` marker, because that marker would point at a file
         that isn't actually present (browser -> 404);
      5. None.

    A ``@file/`` marker is never emitted for an allowlisted name whose file is actually absent
    (broken-marker hardening, symmetric between the blob and dir paths). Used by both ingestion
    paths (init_tables core/external/pro seeding and update_external_plugins) so a rebooted
    scheduler cannot overwrite a detected/declared marker with a stale value."""
    has_data = isinstance(data, (bytes, bytearray, BytesIO))
    if has_data:
        name = detect_plugin_icon(data)
        if name:
            return f"@file/{name}"
    field = icon_field if isinstance(icon_field, str) and icon_field else None
    if not has_data and dir_path is not None:
        if field and field in PLUGIN_ICON_FILES and (Path(dir_path) / field).is_file():
            return f"@file/{field}"
        detected = detect_local_plugin_icon(dir_path)
        if detected:
            return f"@file/{detected}"
        return field
    if field:
        if not has_data and field in PLUGIN_ICON_FILES:
            return f"@file/{field}"
        return field
    return None


def _validate_tar_members(members, *, allow_symlinks=False):
    """Pre-validate tar members before extraction (defense-in-depth against CVE-2025-4517).

    Checks archive metadata only — no disk access — so PATH_MAX symlink chain attacks are impossible.
    When allow_symlinks is False, all symlinks/hardlinks are rejected (matching filter="data").
    When allow_symlinks is True, symlinks are permitted but their targets are still validated.
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
            if not allow_symlinks:
                raise ValueError(f"Tar member {member.name!r} is a symlink/hardlink (not permitted)")
            # Even when symlinks are allowed, validate their targets
            if Path(member.linkname).is_absolute():
                raise ValueError(f"Tar member {member.name!r} links to absolute path {member.linkname!r}")
            # Normalize to collapse valid .. segments, then check if any remain (= escaping)
            normalized = normpath(path_join(str(Path(member.name).parent), member.linkname))
            if ".." in Path(normalized).parts:
                raise ValueError(f"Tar member {member.name!r} links outside target directory")


def safe_tar_extractall(tar, path, *, tar_filter="data", **kwargs):
    """Extract a tar archive safely with pre-validation and Python 3.12+ filter.

    Pre-validates all members before extraction to defend against CVE-2025-4517
    (PATH_MAX symlink chain bypass of tarfile filters). Then applies the filter
    as additional defense-in-depth.

    Use tar_filter="tar" instead of "data" when symlinks must be preserved
    (e.g. Let's Encrypt certs). Use tar_filter="auto" to let the helper pick
    "tar" only when the archive actually contains symlink/hardlink members,
    and fall back to the stricter "data" filter otherwise — useful for
    restoring trusted cache archives that may or may not contain links
    depending on the plugin.
    """
    members_to_check = kwargs.get("members")
    if members_to_check is None:
        members_to_check = tar.getmembers()
    if tar_filter == "auto":
        tar_filter = "tar" if any(m.issym() or m.islnk() for m in members_to_check) else "data"
    _validate_tar_members(members_to_check, allow_symlinks=(tar_filter != "data"))
    try:
        tar.extractall(path, filter=tar_filter, **kwargs)
    except TypeError:
        tar.extractall(path, **kwargs)


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


def get_redis_client(
    use_redis: bool = False,
    redis_host: Optional[str] = None,
    redis_port: Union[str, int] = "6379",
    redis_db: Union[str, int] = "0",
    redis_timeout: Union[str, float] = "1000.0",
    redis_keepalive_pool: Union[str, int] = "10",
    redis_ssl: bool = False,
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
            redis_timeout = float(redis_timeout)

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
                max_connections=redis_keepalive_pool,
            )

            try:
                # Test the connection
                sentinel.discover_master(redis_sentinel_master)

                # Get master connection
                redis_client = sentinel.master_for(
                    redis_sentinel_master,
                    db=redis_db,
                    username=redis_username,
                    password=redis_password,
                )
            except Exception as e:
                if logger:
                    logger.error(f"Failed to connect to Redis Sentinel: {e}")
                return None

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
                max_connections=redis_keepalive_pool,
                ssl=redis_ssl,
            )

        # Test the connection
        redis_client.ping()
        if logger:
            logger.info("Successfully connected to Redis")

        return redis_client

    except Exception as e:
        if logger:
            logger.error(f"Failed to connect to Redis: {e}")
        return None
