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
from typing import Dict, List, Mapping, Optional, Type, Union

from pydantic import ValidationError

from common_utils import bytes_hash  # type: ignore
from letsencrypt_providers import (
    BunnyNetProvider,
    ClouDNSProvider,
    CloudflareProvider,
    DesecProvider,
    DigitalOceanProvider,
    DomainOffensiveProvider,
    DnsimpleProvider,
    DnsMadeEasyProvider,
    DomeneshopProvider,
    DuckDnsProvider,
    DynuProvider,
    GandiProvider,
    GehirnProvider,
    GoDaddyProvider,
    GoogleProvider,
    HetznerProvider,
    InfomaniakProvider,
    IonosProvider,
    LinodeProvider,
    LuaDnsProvider,
    NjallaProvider,
    NSOneProvider,
    OvhProvider,
    Provider,
    PowerdnsProvider,
    Rfc2136Provider,
    Route53Provider,
    SakuraCloudProvider,
    ScalewayProvider,
    TransIPProvider,
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

# Name -> Provider class map. Lives here (not in the job script) so both certbot-new.py
# (issuance) and certbot-renew.py (renewal, via setup_route53_aws_config) resolve DNS
# providers through one shared, importable source of truth.
PROVIDERS: Dict[str, Type[Provider]] = {
    "bunny": BunnyNetProvider,
    "cloudns": ClouDNSProvider,
    "cloudflare": CloudflareProvider,
    "desec": DesecProvider,
    "digitalocean": DigitalOceanProvider,
    "domainoffensive": DomainOffensiveProvider,
    "domeneshop": DomeneshopProvider,
    "dnsimple": DnsimpleProvider,
    "dnsmadeeasy": DnsMadeEasyProvider,
    "duckdns": DuckDnsProvider,
    "dynu": DynuProvider,
    "gandi": GandiProvider,
    "gehirn": GehirnProvider,
    "godaddy": GoDaddyProvider,
    "google": GoogleProvider,
    "hetzner": HetznerProvider,
    "infomaniak": InfomaniakProvider,
    "ionos": IonosProvider,
    "linode": LinodeProvider,
    "luadns": LuaDnsProvider,
    "njalla": NjallaProvider,
    "nsone": NSOneProvider,
    "ovh": OvhProvider,
    "pdns": PowerdnsProvider,
    "rfc2136": Rfc2136Provider,
    "route53": Route53Provider,
    "sakuracloud": SakuraCloudProvider,
    "scaleway": ScalewayProvider,
    "transip": TransIPProvider,
}


def extract_provider(
    service: str,
    credential_key: str,
    authenticator: str = "",
    decode_base64: bool = True,
    logger=None,
) -> Optional[Provider]:
    """Parse ``<credential_key>*`` env vars into a validated DNS :class:`Provider`, or ``None``.

    Shared by issuance (certbot-new) and renewal (certbot-renew, via
    :func:`setup_route53_aws_config`) so both derive identical credentials from a single
    code path. ``credential_key`` is the env-var prefix the caller selects (monosite vs
    multisite ``{service}_`` form); ``service`` is used only for log context. Reads from
    ``os.environ`` directly.
    """
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

    # Process base64 encoded credentials (except for rfc2136)
    if decode_base64 and credential_items:
        for key, value in credential_items.items():
            if authenticator != "rfc2136" and len(value) % 4 == 0 and re_match(r"^[A-Za-z0-9+/=]+$", value):
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

    try:
        return PROVIDERS[authenticator](**credential_items)
    except ValidationError as ve:
        if logger is not None:
            # Never log raw `ve`/`format_exc()`: pydantic v2's ValidationError stringification embeds
            # the raw input dict, which would leak the operator's DNS API token / secret key into the
            # scheduler log. Log only the field locations and error types.
            errors = [(".".join(str(part) for part in err["loc"]), err["type"]) for err in ve.errors()]
            logger.error(f"[Service: {service}] Error while validating credentials, skipping generation: {errors}")
        return None


def write_provider_credentials_file(provider_instance: Provider, data_path: Union[str, Path] = LETSENCRYPT_CACHE_PATH) -> str:
    """Serialise a validated :class:`Provider`'s credentials to disk and return the path.

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


def setup_route53_aws_config(cmd_env: Dict[str, str], data_path: Union[str, Path] = LETSENCRYPT_CACHE_PATH, logger=None) -> List[str]:
    """Point ``cmd_env["AWS_CONFIG_FILE"]`` at the route53 credentials so a blanket
    ``certbot renew`` can authenticate.

    ``certbot-dns-route53`` has no ``--dns-route53-credentials`` flag (it inherits from
    ``common.Plugin``, not ``DNSAuthenticator``) and persists nothing in
    ``renewal/<cert>.conf`` — it reads AWS credentials only from the ``AWS_CONFIG_FILE``
    env var. certbot-new.py sets that per-service at issuance, but certbot-renew.py runs a
    single ``certbot renew`` for every cert, so the renew job must re-derive the route53
    credentials from the plugin settings and set ``AWS_CONFIG_FILE`` up-front. Without
    this, route53 certificates issued with explicit access keys silently fail to auto-renew.

    Reads ``os.environ`` (not ``cmd_env``): :func:`build_certbot_env` has already popped the
    DB-config credential keys from ``cmd_env``, but the process environment still holds them.
    Mirrors certbot-new.py issuance exactly (multisite uses the ``{service}_`` prefix with no
    global fallback). Only route53 DNS-01 services are touched — every other provider keeps
    using its persisted ``--dns-<provider>-credentials`` path. A single route53 account (the
    common case) is fully served by one ``AWS_CONFIG_FILE``; multiple *distinct* accounts
    cannot be expressed through one env var on a single ``certbot renew`` run, so the first is
    used and a warning is logged. Returns the distinct credential file paths discovered.
    """
    paths: List[str] = []

    def _collect(service: str, credential_key: str, dns_provider: str, decode_base64: bool) -> None:
        if dns_provider.lower() != "route53":
            return
        try:
            provider_instance = extract_provider(service, credential_key, "route53", decode_base64, logger)
        except Exception as exc:  # noqa: BLE001 — a bad credential set must never abort the whole renew run
            if logger is not None:
                logger.warning(f"[Service: {service}] could not rebuild route53 credentials for renewal: {exc}")
            return
        if provider_instance is None:
            return
        try:
            path = write_provider_credentials_file(provider_instance, data_path)
        except OSError as exc:
            if logger is not None:
                logger.warning(f"[Service: {service}] failed to write route53 credentials file for renewal: {exc}")
            return
        if path not in paths:
            paths.append(path)

    if getenv("MULTISITE", "no") != "yes":
        if (
            getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
            and getenv("LETS_ENCRYPT_PASSTHROUGH", "no").lower() == "no"
            and getenv("LETS_ENCRYPT_CHALLENGE", "http").lower() == "dns"
        ):
            _collect(
                "default",
                "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM",
                getenv("LETS_ENCRYPT_DNS_PROVIDER", ""),
                getenv("LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64", "yes").lower() == "yes",
            )
    else:
        for first_server in getenv("SERVER_NAME", "www.example.com").split():
            if not first_server:
                continue
            if getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") != "yes":
                continue
            # Mirror issuance: a passthrough service gets no cert, so derive no creds for it.
            if getenv(f"{first_server}_LETS_ENCRYPT_PASSTHROUGH", "no").lower() != "no":
                continue
            if getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http").lower() != "dns":
                continue
            _collect(
                first_server,
                f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM",
                getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER", ""),
                getenv(f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64", "yes").lower() == "yes",
            )

    if not paths:
        return paths

    cmd_env["AWS_CONFIG_FILE"] = paths[0]
    if len(paths) > 1 and logger is not None:
        logger.warning(
            f"{len(paths)} distinct route53 credential sets are configured but `certbot renew` accepts only one "
            f"AWS_CONFIG_FILE per run; using {paths[0]}. Certs on the other route53 account(s) may not auto-renew "
            "— move them to separate BunkerWeb instances or renew them individually."
        )
    return paths


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
from letsencrypt_consistency import le_cache_write_lock, letsencrypt_cache_consistent  # noqa: E402,F401
