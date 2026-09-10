"""Validate Concurrent audit settings; check storage on the instance, never on the scheduler."""

from os import W_OK, X_OK, access, geteuid, getgrouplist, setgid, setgroups, setuid
from pathlib import Path
from pwd import getpwnam
from re import fullmatch
from sys import argv, exit as sys_exit, stderr

from env_file import parse_env_file


def validate_audit_log_settings(config: dict, *, check_storage: bool = False, partial: bool = False) -> None:
    # Unknown prefixes are ignored by Configurator; only registered services are scopes.
    type_key = "MODSECURITY_SEC_AUDIT_LOG_TYPE"
    storage_key = "MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR"
    multisite = config.get("MULTISITE") == "yes"
    service_prefixes = {service + "_" for service in config.get("SERVER_NAME", "").split()} if multisite else {""}
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
        if partial and not storage:
            # A template may supply the directory after raw variables have been checked.
            continue
        if not storage:
            raise ValueError(f"{prefix}{storage_key} is required for Concurrent audit logging")
        if config.get("USE_MODSECURITY_GLOBAL_CRS") == "yes":
            active_scope = not prefix
            enabled = global_crs_enabled
        else:
            active_scope = prefix in http_prefixes
            enabled = config.get(prefix + "USE_MODSECURITY", config.get("USE_MODSECURITY", "yes")) == "yes"
        if check_storage and active_scope and enabled:
            # The standalone process runs with the same credentials as the nginx worker.
            if not Path(storage).is_dir() or not access(storage, W_OK | X_OK):
                raise ValueError(f"{prefix}{storage_key} must already exist and be writable/searchable by the nginx worker: {storage}")


if __name__ == "__main__":
    try:
        config = parse_env_file(Path(argv[1]))
        # FreeBSD's master is root; its workers use nginx. Never check root's access instead.
        if geteuid() == 0 and any(key.endswith("MODSECURITY_SEC_AUDIT_LOG_TYPE") and value == "Concurrent" for key, value in config.items()):
            worker = getpwnam("nginx")
            setgroups(getgrouplist(worker.pw_name, worker.pw_gid))
            setgid(worker.pw_gid)
            setuid(worker.pw_uid)
        validate_audit_log_settings(config, check_storage=True)
        print("ModSecurity audit preflight successful")
    except (OSError, ValueError, KeyError) as exc:
        print(f"ModSecurity audit preflight failed: {exc}", file=stderr)
        sys_exit(1)
