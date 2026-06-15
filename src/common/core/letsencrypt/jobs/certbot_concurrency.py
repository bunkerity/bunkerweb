from contextlib import suppress
from dataclasses import dataclass
from json import loads
from operator import itemgetter
from os import readlink, symlink, walk
from pathlib import Path
from shutil import copy2, copyfileobj, copystat, copytree, rmtree
from subprocess import DEVNULL, PIPE, STDOUT, TimeoutExpired, run
from tempfile import mkdtemp
from typing import Dict, List, Optional, Set, Tuple

from letsencrypt_utils import (
    LETSENCRYPT_PRODUCTION_DIRECTORY,
    LETSENCRYPT_STAGING_DIRECTORY,
    ZEROSSL_DIRECTORY,
    certbot_log_backup_flags,
)


@dataclass(frozen=True)
class CertbotPaths:
    config_dir: Path
    work_dir: Path
    logs_dir: Path


def _merge_dir(src: Path, dest: Path, logger=None) -> None:
    for root, dirs, files in walk(src):
        rel_root = Path(root).relative_to(src)
        dest_root = dest.joinpath(rel_root)
        try:
            dest_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            if logger:
                logger.warning(f"Failed to create directory {dest_root}: {e}")
            continue
        for file_name in files:
            src_file = Path(root).joinpath(file_name)
            dest_file = dest_root.joinpath(file_name)
            try:
                if dest_file.exists() or dest_file.is_symlink():
                    dest_file.unlink()
                if src_file.is_symlink():
                    target = readlink(src_file)
                    symlink(target, dest_file)
                    copystat(src_file, dest_file, follow_symlinks=False)
                else:
                    copy2(src_file, dest_file)
            except OSError as e:
                if logger:
                    logger.warning(f"Failed to merge file {src_file} to {dest_file}: {e}")
                continue


def _merge_logs(src: Path, dest: Path, logger=None) -> None:
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if logger:
            logger.warning(f"Failed to create log directory {dest}: {e}")
        return
    for root, _, files in walk(src):
        rel_root = Path(root).relative_to(src)
        dest_root = dest.joinpath(rel_root)
        try:
            dest_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            if logger:
                logger.warning(f"Failed to create log subdirectory {dest_root}: {e}")
            continue
        for file_name in files:
            src_file = Path(root).joinpath(file_name)
            dest_file = dest_root.joinpath(file_name)
            try:
                if src_file.is_symlink():
                    if dest_file.exists() or dest_file.is_symlink():
                        dest_file.unlink()
                    target = readlink(src_file)
                    symlink(target, dest_file)
                    copystat(src_file, dest_file, follow_symlinks=False)
                    continue
                if dest_file.exists():
                    with src_file.open("rb") as src_handle, dest_file.open("ab") as dest_handle:
                        dest_handle.write(b"\n")
                        copyfileobj(src_handle, dest_handle)
                else:
                    copy2(src_file, dest_file)
            except (OSError, IOError) as e:
                if logger:
                    logger.warning(f"Failed to merge log file {src_file} to {dest_file}: {e}")
                continue


def _server_url_to_subpath(server_url: str) -> str:
    """Map an ACME server URL to the relative path certbot uses under accounts/.

    Certbot constructs `<config-dir>/accounts/<URL minus scheme>/<account-id>` —
    every path segment of the URL becomes a directory segment on disk:

      https://acme-staging-v02.api.letsencrypt.org/directory
        -> acme-staging-v02.api.letsencrypt.org/directory

      https://acme.zerossl.com/v2/DV90
        -> acme.zerossl.com/v2/DV90  (no `/directory` segment, comes from URL)
    """
    url = server_url.strip()
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            url = url.removeprefix(scheme)
            break
    return url.strip("/")


def _scoped_account_root(accounts_root: Path, server_url: str) -> Optional[Path]:
    """Return the directory that immediately contains <account-id>/ subdirs for a CA.

    Returns None when the path doesn't exist (no account registered for this CA yet).
    """
    subpath = _server_url_to_subpath(server_url)
    if not subpath:
        return None
    scoped = accounts_root.joinpath(*subpath.split("/"))
    if not scoped.is_dir():
        return None
    return scoped


def _find_directory_dirs(root: Path) -> List[Path]:
    """Recursively find subdirectories named 'directory' under root (legacy helper).

    Retained for backward compatibility with callers that still use the legacy
    server-agnostic discovery. New code should pass `server_url` to
    select_account_id / _account_exists and use _scoped_account_root which
    correctly handles both Let's Encrypt 2-level paths (with /directory/) and
    ZeroSSL 3-level paths (no /directory/).
    """
    result = []
    with suppress(OSError):
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if child.name == "directory":
                result.append(child)
            else:
                result.extend(_find_directory_dirs(child))
    return result


def _collect_account_candidates(scoped_root: Path) -> List[Tuple[Path, str]]:
    """Walk a CA-scoped accounts directory and collect (path, email) for each
    account containing a regr.json file."""
    candidates: List[Tuple[Path, str]] = []
    with suppress(OSError):
        for account_dir in scoped_root.iterdir():
            if not account_dir.is_dir():
                continue
            if not account_dir.joinpath("regr.json").is_file():
                continue
            meta_email = ""
            meta_path = account_dir.joinpath("meta.json")
            if meta_path.is_file():
                try:
                    meta = loads(meta_path.read_text())
                    if isinstance(meta, dict):
                        meta_email = str(meta.get("email") or "")
                except (OSError, ValueError, KeyError):
                    # Silently skip corrupted meta.json files
                    meta_email = ""
            candidates.append((account_dir, meta_email))
    return candidates


def select_account_id(accounts_root: Path, staging: bool, email: str, server_url: str = "") -> Optional[str]:
    """Select the best matching account id for an ACME registration request.

    When `server_url` is provided, only accounts registered against that exact
    ACME server are considered — required so a Let's Encrypt account is never
    passed as `--account` to a ZeroSSL `certbot certonly` invocation (which
    would fail with AccountNotFound because certbot resolves the path from
    --server, not from the account id).

    When `server_url` is empty, fall back to the legacy server-agnostic walk
    (kept for callers that have not yet been updated).
    """
    if not accounts_root.is_dir():
        return None

    candidates: List[Tuple[Path, str]] = []

    if server_url:
        scoped = _scoped_account_root(accounts_root, server_url)
        if scoped is None:
            return None
        candidates = _collect_account_candidates(scoped)
    else:
        candidates = _collect_account_candidates_legacy(accounts_root, staging)

    if not candidates:
        return None

    if email:
        email_matches = [entry for entry in candidates if entry[1].lower() == email.lower()]
        if email_matches:
            newest = max(email_matches, key=lambda entry: entry[0].stat().st_mtime)
            return newest[0].name
    else:
        no_email = [entry for entry in candidates if not entry[1]]
        if no_email:
            newest = max(no_email, key=lambda entry: entry[0].stat().st_mtime)
            return newest[0].name

    newest = max(candidates, key=lambda entry: entry[0].stat().st_mtime)
    return newest[0].name


def _collect_account_candidates_legacy(accounts_root: Path, staging: bool) -> List[Tuple[Path, str]]:
    """Server-agnostic walk used when callers do not pass `server_url`.

    Walks every `regr.json` under accounts_root (covers both LE 2-level and
    ZeroSSL 3-level paths). Applies the legacy staging/non-staging filter on
    the immediate server-dir name when possible. New callers should prefer
    server_url scoping for correctness.
    """
    candidates: List[Tuple[Path, str]] = []
    with suppress(OSError):
        for regr in accounts_root.rglob("regr.json"):
            account_dir = regr.parent
            if not account_dir.is_dir():
                continue
            # Best-effort staging filter on the first segment of the relative path.
            try:
                first_segment = account_dir.relative_to(accounts_root).parts[0]
            except (ValueError, IndexError):
                first_segment = ""
            is_staging = "staging" in first_segment
            if staging != is_staging:
                continue
            meta_email = ""
            meta_path = account_dir.joinpath("meta.json")
            if meta_path.is_file():
                try:
                    meta = loads(meta_path.read_text())
                    if isinstance(meta, dict):
                        meta_email = str(meta.get("email") or "")
                except (OSError, ValueError, KeyError):
                    meta_email = ""
            candidates.append((account_dir, meta_email))
    return candidates


def _account_exists(accounts_root: Path, staging: bool, email: str, server_url: str = "") -> bool:
    """Return True if an account matching the request already exists on disk.

    Server-scoped when `server_url` is provided (see select_account_id docstring).
    """
    if not accounts_root.is_dir():
        return False

    candidates: List[Tuple[Path, str]] = []

    if server_url:
        scoped = _scoped_account_root(accounts_root, server_url)
        if scoped is None:
            return False
        candidates = _collect_account_candidates(scoped)
    else:
        candidates = _collect_account_candidates_legacy(accounts_root, staging)

    for _, meta_email in candidates:
        if email:
            if meta_email.lower() == email.lower():
                return True
        else:
            if not meta_email:
                return True
    return False


def ensure_accounts(
    requests: Set[Tuple[bool, str]],
    cmd_env: Dict[str, str],
    certbot_bin: str,
    log_level: str,
    data_path: Path,
    work_dir: str,
    logs_dir: str,
    logger,
) -> None:
    accounts_root = data_path.joinpath("accounts")
    for staging, email in sorted(requests, key=itemgetter(0, 1)):
        server_url = LETSENCRYPT_STAGING_DIRECTORY if staging else LETSENCRYPT_PRODUCTION_DIRECTORY
        if _account_exists(accounts_root, staging, email, server_url=server_url):
            continue
        command = [
            certbot_bin,
            "register",
            "-n",
            "--agree-tos",
            "--config-dir",
            data_path.as_posix(),
            "--work-dir",
            work_dir,
            "--logs-dir",
            logs_dir,
            *certbot_log_backup_flags(cmd_env),
        ]
        if staging:
            command.append("--staging")
        if email:
            command.extend(["--email", email])
        else:
            command.append("--register-unsafely-without-email")
        if log_level == "DEBUG":
            command.append("-v")
        try:
            proc = run(
                command,
                stdin=DEVNULL,
                stdout=PIPE,
                stderr=STDOUT,
                text=True,
                env=cmd_env,
                check=False,
                timeout=300,
            )
        except TimeoutExpired:
            logger.error(f"Let's Encrypt account registration timed out after 300s (staging={staging}, email={'set' if email else 'empty'})")
            continue
        if proc.returncode != 0:
            if "existing account" in proc.stdout.lower():
                logger.info(f"Let's Encrypt account already exists (staging={staging}, email={'set' if email else 'empty'}), skipping registration.")
                continue
            logger.error(f"Failed to register Let's Encrypt account (staging={staging}, email={'set' if email else 'empty'}):\n{proc.stdout}")


def ensure_zerossl_accounts(
    requests: Set[Tuple[bool, str]],
    cmd_env: Dict[str, str],
    zerossl_bot_script: str,
    log_level: str,
    data_path: Path,
    work_dir: str,
    logs_dir: str,
    logger,
) -> None:
    """Pre-register ZeroSSL accounts sequentially before concurrent certificate generation.

    Mirrors ``ensure_accounts`` for Let's Encrypt but invokes zerossl-bot.sh so that
    EAB credentials are fetched and the account is registered against the ZeroSSL ACME
    server.  Running this once before spawning threads guarantees that all concurrent
    certbot invocations share a single pre-existing account, avoiding the interactive
    "Please choose an account" prompt that certbot emits when multiple accounts are found.
    """
    accounts_root = data_path.joinpath("accounts")
    for staging, email in sorted(requests, key=itemgetter(0, 1)):
        # ZeroSSL has no separate staging endpoint — the URL is fixed.
        if _account_exists(accounts_root, staging, email, server_url=ZEROSSL_DIRECTORY):
            continue
        command = [
            zerossl_bot_script,
            "register",
            "-n",
            "--agree-tos",
            "--config-dir",
            data_path.as_posix(),
            "--work-dir",
            work_dir,
            "--logs-dir",
            logs_dir,
            *certbot_log_backup_flags(cmd_env),
        ]
        if email:
            command.extend(["--email", email])
        else:
            command.append("--register-unsafely-without-email")
        if staging:
            command.append("--staging")
        if log_level == "DEBUG":
            command.append("-v")
        try:
            proc = run(
                command,
                stdin=DEVNULL,
                stdout=PIPE,
                stderr=STDOUT,
                text=True,
                env=cmd_env,
                check=False,
                timeout=300,
            )
        except TimeoutExpired:
            logger.error(f"ZeroSSL account registration timed out after 300s (email={'set' if email else 'empty'})")
            continue
        if proc.returncode != 0:
            if "existing account" in proc.stdout.lower():
                logger.info(f"ZeroSSL account already exists (email={'set' if email else 'empty'}), skipping registration.")
                continue
            logger.error(f"Failed to register ZeroSSL account (email={'set' if email else 'empty'}):\n{proc.stdout}")


def _rewrite_renewal_paths(paths: CertbotPaths, data_path: Path, work_dir: str, logs_dir: str, logger) -> None:
    renewal_dir = paths.config_dir.joinpath("renewal")
    if not renewal_dir.is_dir():
        return

    replacements = {
        paths.config_dir.as_posix(): data_path.as_posix(),
        paths.work_dir.as_posix(): work_dir,
        paths.logs_dir.as_posix(): logs_dir,
    }

    for conf_file in renewal_dir.glob("*.conf"):
        try:
            content = conf_file.read_text()
        except BaseException as e:
            logger.debug(f"Failed to read renewal config {conf_file}: {e}")
            continue

        updated = content
        for old, new in replacements.items():
            updated = updated.replace(old, new)

        if updated != content:
            try:
                conf_file.write_text(updated)
            except BaseException as e:
                logger.debug(f"Failed to update renewal config {conf_file}: {e}")


def prepare_certbot_paths(
    service: str, concurrent: bool, cache_path: Path, data_path: Path, work_dir: str, logs_dir: str
) -> Tuple[CertbotPaths, Optional[Path]]:
    if not concurrent:
        return CertbotPaths(data_path, Path(work_dir), Path(logs_dir)), None

    cache_path.mkdir(parents=True, exist_ok=True)
    temp_root = Path(mkdtemp(prefix=f"certbot-{service}-", dir=cache_path.as_posix()))
    config_dir = temp_root.joinpath("config")
    work_dir_path = temp_root.joinpath("work")
    logs_dir_path = temp_root.joinpath("logs")
    config_dir.mkdir(parents=True, exist_ok=True)
    work_dir_path.mkdir(parents=True, exist_ok=True)
    logs_dir_path.mkdir(parents=True, exist_ok=True)

    accounts_dir = data_path.joinpath("accounts")
    if accounts_dir.is_dir():
        copytree(accounts_dir, config_dir.joinpath("accounts"), symlinks=True, dirs_exist_ok=True)

    return CertbotPaths(config_dir, work_dir_path, logs_dir_path), temp_root


def finalize_certbot_run(
    paths: CertbotPaths,
    temp_root: Optional[Path],
    success: bool,
    merge_lock,
    data_path: Path,
    work_dir: str,
    logs_dir: str,
    logger,
) -> None:
    if not temp_root:
        return
    with merge_lock:
        if success:
            _rewrite_renewal_paths(paths, data_path, work_dir, logs_dir, logger)
            _merge_dir(paths.config_dir, data_path, logger)
            _merge_dir(paths.work_dir, Path(work_dir), logger)
        _merge_logs(paths.logs_dir, Path(logs_dir), logger)
    try:
        rmtree(temp_root, ignore_errors=False)
    except OSError as e:
        logger.warning(f"Failed to remove temporary directory {temp_root}: {e}")
