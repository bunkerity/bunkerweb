from base64 import b64decode
from contextlib import suppress
from json import loads as json_loads
from os import (
    W_OK,
    X_OK,
    access,
    environ,
    getenv,
    sep,
    umask,
)
from os.path import join
from pathlib import Path
from re import match as re_match, search as re_search
from subprocess import TimeoutExpired
from threading import Thread
from traceback import format_exc
from typing import Callable, Dict, List, Mapping, Optional, Union

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

        # Split on any run of whitespace, not a single literal space, and normalise the key. A
        # leading space made the key empty and surrounding quotes made it unmatchable; either way
        # the item was dropped and the only report was a validation error with no field name. A
        # value with no whitespace at all is still a JSON/base64 blob, which is why the split
        # result is what decides, not the presence of a separator.
        parts = env_value.strip().split(None, 1)
        if len(parts) < 2:
            credential_items["json_data"] = env_value
            continue

        key, value = parts
        # `key = value` and `key =value` both reach here with the `=` leading the value.
        value = value.strip().removeprefix("=")
        credential_items[key.strip("\"' \t").lower()] = value.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()

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


def stream_certbot(process, logger_certbot, timeout: float, on_line: Optional[Callable[[str], None]] = None) -> bool:
    """Log every line certbot writes to stderr, and enforce `timeout` on the run.

    Reading has to happen in its own thread: a `select()` on the pipe reports the raw fd,
    not the buffered reader in front of it, so once a burst has been pulled into the
    userspace buffer the fd looks idle and the buffered lines are never drained. Whatever
    is still buffered when the process exits is then lost, which silently swallows both
    the certbot diagnostics and the stale-account marker `on_line` is watching for.

    Returns False when the process had to be killed for exceeding `timeout`.
    """

    def drain():
        # The pipe can be torn down under the reader once the process is killed.
        with suppress(OSError, ValueError):
            for line in process.stderr:
                stripped = line.strip()
                logger_certbot.info(stripped)
                if on_line is not None:
                    on_line(stripped)

    reader = None
    if process.stderr is not None:
        reader = Thread(target=drain, daemon=True)
        reader.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    finally:
        # Bounded on purpose: certbot's hooks inherit stderr, so a hook that outlives a
        # killed certbot keeps the pipe open and the reader would never see EOF.
        if reader is not None:
            reader.join(timeout=5)

    return not timed_out


STALE_ACCOUNT_MARKERS = ("validate JWS", "acme/acct")


def is_stale_account_line(line: str) -> bool:
    """True when the CA refuses the account itself, so retrying with it can never succeed.

    Two different rejections mean the same thing for us, and they read nothing alike:

        Unable to validate JWS :: Account "https://.../acme/acct/123" not found
        Unable to validate JWS :: Account is not valid, has status "deactivated"

    Only the first was matched before, so a deactivated account was retried forever. Note that
    certbot's own `Account at <path> does not exist` is deliberately NOT matched here: that one is
    a local directory that went missing, which repoint_orphan_renewals repairs without touching
    the CA, and treating it as a rejection would delete an account the CA still considers valid.
    """
    if "Account" not in line or not any(marker in line for marker in STALE_ACCOUNT_MARKERS):
        return False
    return "not found" in line or "is not valid" in line


def stale_account_uri(line: str) -> str:
    """The ACME account URI a stale-account rejection names, or an empty string.

    Only the "not found" phrasing carries one; the deactivated phrasing names no account at all,
    which is why failed_renewal_cert exists as the other way to identify the offender.
    """
    match = re_search(r"https?://\S*?/acme/acct/[A-Za-z0-9_-]+", line)
    return match.group(0) if match else ""


def failed_renewal_cert(line: str) -> str:
    """The lineage named by certbot's per-certificate renewal failure line, or an empty string.

    `certbot renew` reports the lineage and the reason on one line, which is the only reliable way
    to tell which account a rejection carrying no URI belongs to.
    """
    match = re_search(r"Failed to renew certificate (\S+) with error:", line)
    return match.group(1) if match else ""


def account_id_for_cert(data_path: Path, cert_name: str) -> str:
    """The account id a renewal conf names, or an empty string."""
    conf = data_path.joinpath("renewal", f"{cert_name}.conf")
    with suppress(OSError):
        for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep_char, value = line.partition("=")
            if sep_char and key.strip() == "account":
                account_id = value.strip()
                return "" if account_id == "None" else account_id
    return ""


def purge_stale_account(data_path: Path, account_id: str, logger) -> bool:
    """Remove the on-disk ACME account dir whose server-side record was pruned.

    Walks for `<account_id>/regr.json` under accounts/ (CA-agnostic: LE 2-level, ZeroSSL 3-level)
    and retires its parent. Best-effort: failures are logged, not raised, so a retry still runs.

    Certbot records the account id in every renewal conf it writes and nothing rewrites those here,
    so removing the directory strands each conf naming it. ensure_accounts_for_orphans registers a
    replacement and repoint_orphan_renewals moves the confs onto it, both at the start of the next
    job run. Name the stranded confs here anyway, or the cause and the symptom surface in different
    runs and read as unrelated problems.
    """
    accounts_root = data_path.joinpath("accounts")
    if not account_id or not accounts_root.is_dir():
        return False
    purged = False
    try:
        for regr in accounts_root.rglob("regr.json"):
            if regr.parent.name == account_id:
                logger.warning(f"Retiring ACME account {account_id} (the certificate authority no longer accepts it) so the next attempt re-registers.")
                quarantine_account(regr.parent, logger)
                purged = True
                stranded = sorted(orphan["cert_name"] for orphan in detect_orphan_renewals(data_path) if orphan["account"] == account_id)
                if stranded:
                    logger.warning(
                        f"Renewal conf(s) {stranded} still reference ACME account {account_id}; they will be repointed at "
                        "the replacement account on the next Let's Encrypt job run."
                    )
    except OSError as e:
        logger.error(f"Failed to purge stale account {account_id}: {e}")
    return purged


def purge_stale_account_by_uri(data_path: Path, account_uri: str, logger) -> bool:
    """Purge the account whose regr.json records `account_uri`.

    The renew job runs certbot over every lineage at once and pins no `--account`, so the local id
    is not known up front. Certbot stores the account URI the CA assigned in regr.json
    (`{"body": {}, "uri": ...}`), which is exactly what the rejection names, so the two can be
    matched without guessing.
    """
    accounts_root = data_path.joinpath("accounts")
    if not account_uri or not accounts_root.is_dir():
        return False
    with suppress(OSError):
        for regr in accounts_root.rglob("regr.json"):
            with suppress(OSError, ValueError):
                if json_loads(regr.read_text(encoding="utf-8")).get("uri") == account_uri:
                    return purge_stale_account(data_path, regr.parent.name, logger)
    logger.error(f"CA rejected ACME account {account_uri} but no local account records that URI; cannot purge it automatically.")
    return False


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
    detect_orphan_renewals,
    le_cache_write_lock,
    letsencrypt_cache_consistent,
    purge_lineage,
    quarantine_account,
    repoint_orphan_renewals,
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
    """Repair the LE tree on disk and persist it back to the DB cache.

    Two repairs, both of which stick only if they are written back: a broken lineage (see
    detect_broken_lineages) makes `certbot certificates`/`renew` fail to parse, and a renewal conf
    naming a deleted ACME account makes every renewal fail AccountNotFound. Because the whole etc/
    tree is one DB cache blob restored on every job start, either break reappears forever unless it
    is both fixed AND written back -- and where there is no blob to restore from, as on a Kubernetes
    node whose cache volume outlives the database, the damage on disk is all there is.

    Returns the quarantined cert names -- that value gates the "no live certs" data-loss check in
    the callers, so repointed confs deliberately do not count towards it.
    """
    # Snapshot the cache-row checksum BEFORE repairing. Job.__init__ restored data_path OUTSIDE
    # le_cache_write_lock, so a UI heal that rewrites the row after our restore must not be
    # clobbered by persisting our stale pre-heal snapshot (which would resurrect a healed orphan).
    file_name = f"folder:{data_path.as_posix()}.tgz"
    before = _le_cache_checksum(job, file_name)
    repointed = repoint_orphan_renewals(data_path, logger)
    names = sanitize_le_cache(data_path, logger)
    # A partial repair is persisted even when the tree is still inconsistent overall. A repoint only
    # ever rewrites `account` to an id that exists, so it cannot add an orphan: the result is
    # strictly closer to consistent than the row it replaces. Withholding the write instead threw
    # away every conf that was repaired because of one that could not be, and since the whole tree
    # is one blob restored on each job start, that repair was redone and discarded on every run.
    if (names or repointed) and getattr(job, "restore_ok", False):
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
