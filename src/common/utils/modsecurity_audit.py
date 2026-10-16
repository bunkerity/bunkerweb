"""Validate Concurrent audit settings; prepare and check their storage on the instance, never on the scheduler."""

from os import W_OK, X_OK, access, geteuid, getgrouplist, setgid, setgroups, setuid
from pathlib import Path
from pwd import getpwnam
from re import fullmatch
from sys import argv, exit as sys_exit, stderr

from env_file import parse_env_file

# Audit records carry request headers and bodies: what this module creates is never readable by "other".
STORAGE_DIR_MODE = 0o750

# The reserved catch-all service renders a curated plugin subset that has no ModSecurity (see
# utils/default_server.py), so it is in the SERVER_NAME roster but is not an audit scope. Spelled out
# here rather than imported: this file also runs standalone on the instance, where the import chain of
# default_server.py is not worth carrying for one constant.
RESERVED_DEFAULT_SERVER = "default-server"


def create_storage_dir(storage: str) -> None:
    """Create `storage` and the missing parents it needs, each `STORAGE_DIR_MODE`, owned by the running user.

    Every component is created and chmod-ed on its own: `mkdir(mode=)` is filtered by the umask and
    `Path.mkdir(parents=True)` gives the parents the default mode, so either alone can leave a world-accessible
    audit directory behind a permissive umask. An existing directory is never touched, whatever its mode: an
    operator who provisioned it (1.6 required that) owns it.
    """
    missing = []
    path = Path(storage)
    while not path.is_dir():
        missing.append(path)
        if path.parent == path:
            break
        path = path.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(STORAGE_DIR_MODE)
        except FileExistsError:
            continue
        directory.chmod(STORAGE_DIR_MODE)


def validate_audit_log_settings(config: dict, *, check_storage: bool = False, create_storage: bool = False, partial: bool = False) -> None:
    """Raise `ValueError` on an invalid audit candidate.

    `check_storage` also requires every active Concurrent scope's directory to exist and be writable by the
    current user; `create_storage` creates a missing one first. Only the instance-side preflight sets them: the
    scheduler runs as another user, on another host in the multi-instance case, and must not judge the disk.
    """
    # Unknown prefixes are ignored by Configurator; only registered services are scopes.
    type_key = "MODSECURITY_SEC_AUDIT_LOG_TYPE"
    storage_key = "MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR"
    multisite = config.get("MULTISITE") == "yes"
    services = [service for service in config.get("SERVER_NAME", "").split() if service != RESERVED_DEFAULT_SERVER] if multisite else []
    service_prefixes = {service + "_" for service in services} if multisite else {""}
    prefixes = {""} | service_prefixes
    http_prefixes = {prefix for prefix in service_prefixes if config.get(prefix + "SERVER_TYPE", config.get("SERVER_TYPE", "http")) == "http"}
    global_crs_enabled = any(config.get(prefix + "USE_MODSECURITY", config.get("USE_MODSECURITY", "yes")) == "yes" for prefix in http_prefixes)
    for prefix in sorted(prefixes):
        log_type = config.get(prefix + type_key, config.get(type_key, "Serial"))
        if log_type not in ("Serial", "Concurrent"):
            raise ValueError(f"{prefix}{type_key} must be Serial or Concurrent")
        storage = config.get(prefix + storage_key, config.get(storage_key, ""))
        # Validate explicit paths before template resolution can change Serial to Concurrent.
        if storage and (not fullmatch(r"/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+/?", storage) or ".." in Path(storage).parts):
            raise ValueError(f"{prefix}{storage_key} must be an absolute directory path without traversal or special characters")
        if log_type == "Serial":
            continue
        if config.get("USE_MODSECURITY_GLOBAL_CRS") == "yes":
            active_scope = not prefix
            enabled = global_crs_enabled
        else:
            active_scope = prefix in http_prefixes
            enabled = config.get(prefix + "USE_MODSECURITY", config.get("USE_MODSECURITY", "yes")) == "yes"
        # An inactive scope is only a fallback for services that override it. Requiring a storage
        # directory there rejects a global Concurrent whose services each set their own, and a
        # service that has ModSecurity disabled entirely.
        if not (active_scope and enabled):
            continue
        if partial and not storage:
            # A template may supply the directory after raw variables have been checked.
            continue
        if not storage:
            raise ValueError(f"{prefix}{storage_key} is required for Concurrent audit logging")
        if create_storage:
            try:
                create_storage_dir(storage)
            except OSError as exc:
                raise ValueError(f"{prefix}{storage_key} cannot be created by the nginx worker: {storage} ({exc.strerror or exc})") from exc
        if check_storage:
            # The standalone process runs with the same credentials as the nginx worker.
            if not Path(storage).is_dir() or not access(storage, W_OK | X_OK):
                raise ValueError(f"{prefix}{storage_key} must already exist and be writable/searchable by the nginx worker: {storage}")


if __name__ == "__main__":
    try:
        config = parse_env_file(Path(argv[1]))
        # FreeBSD's master is root; its workers use nginx. Never check root's access instead, and never
        # create a directory root would own.
        if geteuid() == 0 and any(key.endswith("MODSECURITY_SEC_AUDIT_LOG_TYPE") and value == "Concurrent" for key, value in config.items()):
            worker = getpwnam("nginx")
            setgroups(getgrouplist(worker.pw_name, worker.pw_gid))
            setgid(worker.pw_gid)
            setuid(worker.pw_uid)
        validate_audit_log_settings(config, check_storage=True, create_storage=True)
        print("ModSecurity audit preflight successful")
    except (OSError, ValueError, KeyError, IndexError) as exc:
        print(f"ModSecurity audit preflight failed: {exc}", file=stderr)
        sys_exit(1)
