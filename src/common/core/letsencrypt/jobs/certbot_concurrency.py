from dataclasses import dataclass
from json import loads
from operator import itemgetter
from os import readlink, symlink, walk
from pathlib import Path
from shutil import copy2, copyfileobj, copystat, copytree, rmtree
from subprocess import DEVNULL, PIPE, STDOUT, run
from tempfile import mkdtemp
from typing import Dict, List, Optional, Set, Tuple


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


def select_account_id(accounts_root: Path, staging: bool, email: str) -> Optional[str]:
    if not accounts_root.is_dir():
        return None

    server_dirs = [path for path in accounts_root.iterdir() if path.is_dir()]
    if not server_dirs:
        return None

    if staging:
        preferred = [path for path in server_dirs if "staging" in path.name]
    else:
        preferred = [path for path in server_dirs if "staging" not in path.name]

    if preferred:
        server_dirs = preferred

    candidates: List[Tuple[Path, str]] = []
    for server_dir in server_dirs:
        directory_dir = server_dir.joinpath("directory")
        if not directory_dir.is_dir():
            continue
        for account_dir in directory_dir.iterdir():
            if not account_dir.is_dir():
                continue
            meta_path = account_dir.joinpath("meta.json")
            meta_email = ""
            if meta_path.is_file():
                try:
                    meta = loads(meta_path.read_text())
                    if isinstance(meta, dict):
                        meta_email = str(meta.get("email") or "")
                except (OSError, ValueError, KeyError):
                    # Silently skip corrupted meta.json files
                    meta_email = ""
            candidates.append((account_dir, meta_email))

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


def _account_exists(accounts_root: Path, staging: bool, email: str) -> bool:
    if not accounts_root.is_dir():
        return False

    server_dirs = [path for path in accounts_root.iterdir() if path.is_dir()]
    if not server_dirs:
        return False

    if staging:
        server_dirs = [path for path in server_dirs if "staging" in path.name]
    else:
        server_dirs = [path for path in server_dirs if "staging" not in path.name]

    for server_dir in server_dirs:
        directory_dir = server_dir.joinpath("directory")
        if not directory_dir.is_dir():
            continue
        for account_dir in directory_dir.iterdir():
            if not account_dir.is_dir():
                continue
            meta_path = account_dir.joinpath("meta.json")
            meta_email = ""
            if meta_path.is_file():
                try:
                    meta = loads(meta_path.read_text())
                    if isinstance(meta, dict):
                        meta_email = str(meta.get("email") or "")
                except (OSError, ValueError, KeyError):
                    # Silently skip corrupted meta.json files
                    meta_email = ""
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
        if _account_exists(accounts_root, staging, email):
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
        ]
        if staging:
            command.append("--staging")
        if email:
            command.extend(["--email", email])
        else:
            command.append("--register-unsafely-without-email")
        if log_level == "DEBUG":
            command.append("-v")
        proc = run(
            command,
            stdin=DEVNULL,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            env=cmd_env,
            check=False,
        )
        if proc.returncode != 0:
            if "existing account" in proc.stdout.lower():
                logger.info(f"Let's Encrypt account already exists (staging={staging}, email={'set' if email else 'empty'}), skipping registration.")
                continue
            logger.error(f"Failed to register Let's Encrypt account (staging={staging}, email={'set' if email else 'empty'}):\n{proc.stdout}")


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
