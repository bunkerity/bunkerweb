from base64 import b64decode
from json import loads as json_loads
from os import (
    O_CREAT,
    O_NOFOLLOW,
    O_TRUNC,
    O_WRONLY,
    W_OK,
    X_OK,
    access,
    close as os_close,
    environ,
    fsync as os_fsync,
    getenv,
    open as os_open,
    sep,
    umask,
    write as os_write,
)
from os.path import join
from pathlib import Path
from re import match as re_match
from traceback import format_exc
from typing import Dict, List, Mapping, Optional, Union

from common_utils import bytes_hash  # type: ignore
from letsencrypt_providers import (  # noqa: F401 — is_supported_provider/SUPPORTED_PROVIDER_INPUTS re-exported for the job scripts
    DnsMultiProvider,
    SUPPORTED_PROVIDER_INPUTS,
    is_base64_skip_code,
    is_supported_provider,
    resolve_lego_code,
    translate_credentials,
)

CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")
LETSENCRYPT_PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
LETSENCRYPT_JOBS_PATH = LETSENCRYPT_PLUGIN_PATH.joinpath("jobs")
ZEROSSL_BOT_SCRIPT = LETSENCRYPT_PLUGIN_PATH.joinpath("lib", "zerossl-bot.sh")
LETSENCRYPT_CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
LETSENCRYPT_DATA_PATH = LETSENCRYPT_CACHE_PATH.joinpath("etc")
LETSENCRYPT_WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LETSENCRYPT_LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

LETSENCRYPT_PRODUCTION_DIRECTORY = "https://acme-v02.api.letsencrypt.org/directory"
LETSENCRYPT_STAGING_DIRECTORY = "https://acme-staging-v02.api.letsencrypt.org/directory"
ZEROSSL_DIRECTORY = "https://acme.zerossl.com/v2/DV90"


def extract_provider(
    service: str,
    credential_key: str,
    authenticator: str = "",
    decode_base64: bool = True,
    logger=None,
) -> Optional[DnsMultiProvider]:
    """Parse ``<credential_key>*`` env vars into a :class:`DnsMultiProvider`, or ``None``.

    ``authenticator`` is the operator-facing provider name (``LETS_ENCRYPT_DNS_PROVIDER``),
    e.g. ``cloudflare`` or a lego code; it is resolved to a lego code and the credential
    items are translated to lego env-var names by ``translate_credentials``.
    ``credential_key`` is the env-var prefix the caller selects (monosite vs multisite
    ``{service}_`` form); ``service`` is used only for log context. Reads ``os.environ``.
    """
    lego_code = resolve_lego_code(authenticator)
    if lego_code is None:
        if logger is not None:
            logger.error(f"[Service: {service}] Unknown DNS provider '{authenticator}', skipping generation.")
        return None

    credential_items: Dict[str, str] = {}

    # Collect all credential items
    for env_key, env_value in environ.items():
        if not env_value or not env_key.startswith(credential_key):
            continue

        if " " not in env_value:
            credential_items["json_data"] = env_value
            continue

        key, value = env_value.split(" ", 1)
        credential_items[key.lower()] = value.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()

    # Handle JSON data
    if "json_data" in credential_items:
        value = credential_items.pop("json_data")
        if decode_base64 and not credential_items and len(value) % 4 == 0 and re_match(r"^[A-Za-z0-9+/=]+$", value):
            try:
                decoded = b64decode(value).decode("utf-8")
                json_data = json_loads(decoded)
                if isinstance(json_data, dict):
                    credential_items = {
                        k.lower(): str(v).removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                        for k, v in json_data.items()
                    }
            except BaseException:
                if logger is not None:
                    logger.debug(format_exc())

    # Process base64 encoded credentials (except for providers whose secrets are legitimately base64, e.g. rfc2136/dnsupdate TSIG)
    if decode_base64 and credential_items and not is_base64_skip_code(lego_code):
        for key, value in credential_items.items():
            if len(value) % 4 == 0 and re_match(r"^[A-Za-z0-9+/=]+$", value):
                try:
                    decoded = b64decode(value).decode("utf-8")
                    if decoded != value:
                        credential_items[key] = decoded.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                except BaseException:
                    if logger is not None:
                        logger.debug(format_exc())

    if not credential_items:
        if logger is not None:
            logger.warning(f"[Service: {service}] DNS challenge selected but no DNS credentials are configured, skipping generation.")
        return None

    # translate_credentials logs a precise, secret-free reason (unknown key / missing required env)
    # and returns None on failure, preserving the "return None -> deactivate this service" contract.
    provider = translate_credentials(lego_code, authenticator, credential_items, logger)
    if provider is not None and provider.sidecars:
        # Finalize sidecar file references (e.g. google's GCE_SERVICE_ACCOUNT_FILE) to their
        # deterministic cache path now, so the credentials INI body is stable across runs; the
        # sidecar file itself is written/cached at issuance time by certbot-new.py.
        for basename, (_content, env_key) in provider.sidecars.items():
            provider.env[env_key] = LETSENCRYPT_CACHE_PATH.joinpath(basename).as_posix()
    return provider


def write_provider_credentials_file(provider_instance: DnsMultiProvider, data_path: Union[str, Path] = LETSENCRYPT_CACHE_PATH) -> str:
    """Serialise a :class:`DnsMultiProvider`'s credentials to disk and return the path.

    Filename is ``credentials_<bytes_hash(body)[:12]>.<ext>`` — identical to the scheme
    certbot-new.py uses at issuance, so the file written here resolves to the same path
    certbot already references (no second file accretes). Written with the final ``0o600``
    perms baked into ``open(2)`` plus ``O_NOFOLLOW`` (no world-readable window, no symlink
    swap). Idempotent: same credentials -> same path, ``O_TRUNC`` rewrites identical bytes.
    """
    formatted = provider_instance.get_formatted_credentials()
    ext = provider_instance.get_file_type()
    cred_hash = bytes_hash(formatted, algorithm="sha256")[:12]
    cred_file = Path(data_path).joinpath(f"credentials_{cred_hash}.{ext}")
    cred_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os_open(cred_file.as_posix(), O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW, 0o600)
    try:
        os_write(fd, formatted)
        os_fsync(fd)
    finally:
        os_close(fd)
    return cred_file.as_posix()


def certbot_log_backup_flags(env_vars: Optional[Mapping[str, str]] = None) -> List[str]:
    """Return `--max-log-backups N` to cap certbot's per-invocation log rotations.

    Certbot defaults to backupCount=1000, which piles up ~1000 rotation files per logs-dir.
    Operators tune this via `LETS_ENCRYPT_MAX_LOG_BACKUPS` (default 50).
    """
    raw = (env_vars or environ).get("LETS_ENCRYPT_MAX_LOG_BACKUPS", "50").strip()
    try:
        value = max(0, int(raw))
    except ValueError:
        value = 50
    return ["--max-log-backups", str(value)]


_API_SETTINGS_WHITELIST = frozenset(
    {
        "API_HTTP_PORT",
        "API_HTTPS_PORT",
        "API_LISTEN_IP",
        "API_LISTEN_HTTP",
        "API_LISTEN_HTTPS",
        "API_SERVER_NAME",
        "API_TOKEN",
        "API_WHITELIST_IP",
    }
)


def add_internal_api_env(cmd_env: Dict[str, str], env_vars: Optional[Mapping[str, str]] = None) -> None:
    """Re-add internal API env vars removed with DB config keys."""
    if env_vars is None:
        env_vars = environ
    for key in _API_SETTINGS_WHITELIST:
        value = env_vars.get(key)
        if value:
            cmd_env[key] = value


def build_certbot_env(job, deps_path: str, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build a clean certbot execution environment from process env + job DB config."""
    cmd_env = dict(base_env) if base_env is not None else environ.copy()

    db_config = job.db.get_config()
    for key in db_config:
        cmd_env.pop(key, None)

    current_pythonpath = cmd_env.get("PYTHONPATH", "")
    pythonpath_entries = [entry for entry in current_pythonpath.split(":") if entry]
    if deps_path not in pythonpath_entries:
        pythonpath_entries.append(deps_path)
    cmd_env["PYTHONPATH"] = ":".join(pythonpath_entries)

    database_uri = getenv("DATABASE_URI", "")
    if database_uri:
        cmd_env["DATABASE_URI"] = database_uri

    add_internal_api_env(cmd_env)
    return cmd_env


def prepare_logs_dir(logs_dir: Union[str, Path], logger) -> None:
    """Ensure the Let's Encrypt logs directory is writable by the running user."""
    try:
        umask(0o007)
    except BaseException:
        logger.debug("Failed to set umask to 007 for letsencrypt logs")

    logs_path = Path(logs_dir)
    try:
        logs_path.mkdir(parents=True, exist_ok=True)
    except BaseException as e:
        logger.error(f"Failed to create Let's Encrypt logs directory {logs_path}: {e}")
        return

    try:
        logs_path.chmod(0o2770)
    except BaseException as e:
        logger.debug(f"Failed to set permissions on {logs_path}: {e}")

    for log_file in logs_path.glob("*.log*"):
        try:
            if access(log_file, W_OK):
                log_file.chmod(0o660)
            else:
                logger.warning(f"Removing unwritable Let's Encrypt log file {log_file}")
                log_file.unlink(missing_ok=True)
        except BaseException as e:
            logger.debug(f"Failed to adjust permissions on log file {log_file}: {e}")


def is_zerossl_used_in_env(env_vars: Optional[Mapping[str, str]] = None) -> bool:
    """Return True when at least one active service uses LETS_ENCRYPT_SERVER=zerossl."""
    if env_vars is None:
        env_vars = environ

    if env_vars.get("MULTISITE", "no") != "yes":
        return env_vars.get("AUTO_LETS_ENCRYPT", "no") == "yes" and env_vars.get("LETS_ENCRYPT_SERVER", "letsencrypt").lower() == "zerossl"

    for first_server in env_vars.get("SERVER_NAME", "www.example.com").split():
        if not first_server:
            continue
        if env_vars.get(f"{first_server}_AUTO_LETS_ENCRYPT", "no") != "yes":
            continue
        if env_vars.get(f"{first_server}_LETS_ENCRYPT_SERVER", env_vars.get("LETS_ENCRYPT_SERVER", "letsencrypt")).lower() == "zerossl":
            return True
    return False


def resolve_certbot_entrypoint(
    acme_server: str,
    certbot_bin: str,
    zerossl_bot_script: Path,
    logger,
    cmd_env: Optional[Dict[str, str]] = None,
    fallback_to_certbot: bool = False,
) -> List[str]:
    """Resolve which executable to use for ACME operations."""
    if acme_server != "zerossl":
        return [certbot_bin]

    if zerossl_bot_script.is_file() and access(zerossl_bot_script, X_OK):
        if cmd_env is not None:
            cmd_env["CERTBOT_BIN"] = certbot_bin
        return [zerossl_bot_script.as_posix()]

    message = f"ZeroSSL is enabled but zerossl-bot is missing or not executable ({zerossl_bot_script})."
    if fallback_to_certbot:
        logger.warning(f"{message} Falling back to certbot.")
        return [certbot_bin]

    logger.error(message)
    return []


def get_expected_acme_directory(server: str, staging: bool) -> str:
    if server == "zerossl":
        return ZEROSSL_DIRECTORY
    if staging:
        return LETSENCRYPT_STAGING_DIRECTORY
    return LETSENCRYPT_PRODUCTION_DIRECTORY


# letsencrypt_cache_consistent has been lifted to src/common/utils/letsencrypt_consistency.py
# so the UI blueprint and the scheduler jobs share one source of truth. The previous
# byte-identical UI copy already drifted multiple times — that bug class is closed by
# re-exporting from a single module instead of maintaining parallel implementations.
from letsencrypt_consistency import (  # noqa: E402,F401
    detect_broken_lineages,
    le_cache_write_lock,
    letsencrypt_cache_consistent,
    purge_lineage,
    sanitize_le_cache,
)

# Sentinel distinguishing "cache-row lookup failed" (degrade to persisting) from "row absent"
# (checksum None, a legitimate value) in the optimistic-concurrency check below.
_LE_READ_ERROR = object()


def _le_cache_checksum(job, file_name: str):
    """Return the LE cache row's current DB checksum, None if the row is absent, or
    _LE_READ_ERROR if the lookup itself failed (caller then degrades to persisting)."""
    try:
        info = job.db.get_job_cache_file(job.job_name, file_name, with_info=True, with_data=False)
    except BaseException:
        return _LE_READ_ERROR
    if isinstance(info, dict):
        return info.get("checksum")
    return None


def sanitize_and_persist(job, data_path: Path, logger) -> List[str]:
    """Quarantine broken renewal lineages and persist the cleaned tree back to the DB cache.

    A broken lineage (see detect_broken_lineages) makes `certbot certificates`/`renew` fail to
    parse, and because the whole etc/ tree is one DB cache blob restored on every job start, the
    break reappears forever unless it is both removed AND written back. When something was
    quarantined and the initial restore succeeded, re-cache immediately so the fix survives the
    next restore. Returns the quarantined cert names.
    """
    # Snapshot the cache-row checksum BEFORE sanitizing. Job.__init__ restored data_path OUTSIDE
    # le_cache_write_lock, so a UI heal that rewrites the row after our restore must not be
    # clobbered by persisting our stale pre-heal snapshot (which would resurrect a healed orphan).
    file_name = f"folder:{data_path.as_posix()}.tgz"
    before = _le_cache_checksum(job, file_name)
    names = sanitize_le_cache(data_path, logger)
    if names and getattr(job, "restore_ok", False):
        try:
            with le_cache_write_lock():
                # Re-read under the lock: if the row changed since our restore, our tree is stale.
                current = _le_cache_checksum(job, file_name)
                if _LE_READ_ERROR not in (before, current) and before != current:
                    logger.warning("LE cache row changed since restore; skipping sanitize persist, will retry next run")
                    return names
                if _LE_READ_ERROR in (before, current):
                    logger.debug("LE cache checksum unavailable; persisting sanitized cache without concurrency check")
                cached, err = job.cache_dir(data_path)
            if not cached:
                logger.error(f"Failed to persist sanitized Let's Encrypt cache: {err}")
        except BaseException as e:
            logger.error(f"Exception while persisting sanitized Let's Encrypt cache: {e}")
    return names
