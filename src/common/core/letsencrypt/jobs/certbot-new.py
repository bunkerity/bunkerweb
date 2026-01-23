#!/usr/bin/env python3

from base64 import b64decode
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from json import loads
from os import W_OK, access, environ, getenv, sep, umask
from os.path import join
from pathlib import Path
from re import MULTILINE, match, search
from select import select
from subprocess import DEVNULL, PIPE, STDOUT, Popen, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from threading import Event, Lock, Thread
from traceback import format_exc
from typing import Dict, List, Optional, Set, Tuple, Type, Union
from certbot_concurrency import (
    CertbotPaths,
    ensure_accounts,
    finalize_certbot_run,
    prepare_certbot_paths,
    select_account_id,
)


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from pydantic import ValidationError
from requests import get

from common_utils import bytes_hash, effective_cpu_count, file_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

from letsencrypt_providers import (
    BunnyNetProvider,
    CloudflareProvider,
    DesecProvider,
    DigitalOceanProvider,
    DomainOffensiveProvider,
    DnsimpleProvider,
    DnsMadeEasyProvider,
    DomeneshopProvider,
    DuckDnsProvider,
    DynuProvider,
    GehirnProvider,
    GoDaddyProvider,
    GoogleProvider,
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

LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper()
LOGGER = getLogger("LETS-ENCRYPT.NEW")
LOGGER_CERTBOT = getLogger("LETS-ENCRYPT.NEW.CERTBOT")

CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")
PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")
MERGE_LOCK = Lock()
RUNNING_LOCK = Lock()
RUNNING_CERTBOT = 0
MONITOR_STOP = Event()
MONITOR_THREAD: Optional[Thread] = None


def _monitor_certbot_progress() -> None:
    while not MONITOR_STOP.wait(10):
        with RUNNING_LOCK:
            running = RUNNING_CERTBOT
        if running > 0:
            LOGGER.info("⏳ Still generating certificate(s)...")


def start_progress_monitor() -> None:
    global MONITOR_THREAD
    if MONITOR_THREAD and MONITOR_THREAD.is_alive():
        return
    MONITOR_STOP.clear()
    MONITOR_THREAD = Thread(target=_monitor_certbot_progress, daemon=True)
    MONITOR_THREAD.start()


def stop_progress_monitor() -> None:
    global MONITOR_THREAD
    MONITOR_STOP.set()
    if MONITOR_THREAD:
        MONITOR_THREAD.join(timeout=2)
        MONITOR_THREAD = None


def prepare_logs_dir() -> None:
    """Ensure the Let's Encrypt logs directory is writable by the running user.

    In some upgrades the existing letsencrypt.log could be left owned by root
    with read-only group permissions, which prevents certbot from writing new
    entries when the scheduler runs as a non-root user. We normalise the folder
    permissions, relax the umask to keep group write access, and drop any
    unwritable log files so certbot can recreate them.
    """

    try:
        umask(0o007)
    except BaseException:
        LOGGER.debug("Failed to set umask to 007 for letsencrypt logs")

    logs_path = Path(LOGS_DIR)

    try:
        logs_path.mkdir(parents=True, exist_ok=True)
    except BaseException as e:
        LOGGER.error(f"Failed to create Let's Encrypt logs directory {logs_path}: {e}")
        return

    try:
        logs_path.chmod(0o2770)
    except BaseException as e:
        LOGGER.debug(f"Failed to set permissions on {logs_path}: {e}")

    for log_file in logs_path.glob("*.log*"):
        try:
            if access(log_file, W_OK):
                log_file.chmod(0o660)
            else:
                LOGGER.warning(f"Removing unwritable Let's Encrypt log file {log_file}")
                log_file.unlink(missing_ok=True)
        except BaseException as e:
            LOGGER.debug(f"Failed to adjust permissions on log file {log_file}: {e}")


IS_MULTISITE = getenv("MULTISITE", "no") == "yes"
CHALLENGE_TYPES = ("http", "dns")
PROFILE_TYPES = ("classic", "tlsserver", "shortlived")
DNS_PROPAGATION_DEFAULT = "default"


def normalize_server_names(server_names: str) -> Set[str]:
    """Return a normalized set of server names split on comma/space, lowercased and trimmed."""
    return {part.strip().lower() for part in server_names.replace(",", " ").split() if part.strip()}


def filter_wildcard_names(names: Set[str]) -> Set[str]:
    """Drop wildcard entries (e.g. '*.example.com') from a set of server names."""
    return {name for name in names if not name.startswith("*.")}


def format_server_names(names: Set[str]) -> str:
    """Return a deterministic, certbot-friendly server names string."""
    return ",".join(sorted(names, key=lambda value: (0 if value.startswith("*.") else 1, value)))


def parse_certbot_domains(certificate_block: str) -> str:
    match = search(r"^\s*(Domains|Identifiers):\s+(.+)$", certificate_block, MULTILINE)
    if not match:
        return ""
    return " ".join(match.group(2).split()).replace(" ", ",")


PROVIDERS: Dict[str, Type[Provider]] = {
    "bunny": BunnyNetProvider,
    "cloudflare": CloudflareProvider,
    "desec": DesecProvider,
    "digitalocean": DigitalOceanProvider,
    "domainoffensive": DomainOffensiveProvider,
    "domeneshop": DomeneshopProvider,
    "dnsimple": DnsimpleProvider,
    "dnsmadeeasy": DnsMadeEasyProvider,
    "duckdns": DuckDnsProvider,
    "dynu": DynuProvider,
    "gehirn": GehirnProvider,
    "godaddy": GoDaddyProvider,
    "google": GoogleProvider,
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

status = 0

PSL_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
PSL_STATIC_FILE = "public_suffix_list.dat"
psl_lines = None
psl_rules = None


def load_public_suffix_list(job):
    job_cache = job.get_cache(PSL_STATIC_FILE, with_info=True, with_data=True)
    if (
        isinstance(job_cache, dict)
        and job_cache.get("last_update")
        and job_cache["last_update"] > (datetime.now().astimezone() - timedelta(days=1)).timestamp()
    ):
        return job_cache["data"].decode("utf-8").splitlines()

    try:
        resp = get(PSL_URL, timeout=8)
        resp.raise_for_status()
        content = resp.text
        cached, err = job.cache_file(PSL_STATIC_FILE, content.encode("utf-8"))
        if not cached:
            LOGGER.error(f"Error while saving public suffix list to cache : {err}")
        return content.splitlines()
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while downloading public suffix list: {e}")
        if isinstance(job_cache, dict):
            return job_cache.get("data", b"").decode("utf-8").splitlines()
        return []


def parse_psl(psl_lines):
    # Parse PSL lines into rules and exceptions sets
    rules = set()
    exceptions = set()
    for line in psl_lines:
        line = line.strip()
        if not line or line.startswith("//"):
            continue  # Ignore empty lines and comments
        if line.startswith("!"):
            exceptions.add(line[1:])  # Exception rule
            continue
        rules.add(line)  # Normal or wildcard rule
    return {"rules": rules, "exceptions": exceptions}


def is_domain_blacklisted(domain, psl):
    # Returns True if the domain is forbidden by PSL rules
    domain = domain.lower().strip(".")
    labels = domain.split(".")
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        # Allow if candidate is an exception
        if candidate in psl["exceptions"]:
            return False
        # Block if candidate matches a PSL rule
        if candidate in psl["rules"]:
            if i == 0:
                return True  # Block exact match
            if i == 0 and domain.startswith("*."):
                return True  # Block wildcard for the rule itself
            if i == 0 or (i == 1 and labels[0] == "*"):
                return True  # Block *.domain.tld
            if len(labels[i:]) == len(labels):
                return True  # Block domain.tld
            # Allow subdomains
        # Block if candidate matches a PSL wildcard rule
        if f"*.{candidate}" in psl["rules"]:
            if len(labels[i:]) == 2:
                return True  # Block foo.bar and *.foo.bar
    return False


def check_psl_blacklist(domains: List[str], psl_rules: Dict, service_name: str) -> bool:
    """Check if any domains are blacklisted by PSL rules."""
    for domain in domains:
        if is_domain_blacklisted(domain, psl_rules):
            LOGGER.error(f"Domain {domain} is blacklisted by Public Suffix List, refusing certificate request for {service_name}.")
            return True
    return False


def extract_provider(service: str, authenticator: str = "", decode_base64: bool = True) -> Optional[Provider]:
    credential_key = f"{service}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" if IS_MULTISITE else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
    credential_items = {}

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
        if decode_base64 and not credential_items and len(value) % 4 == 0 and match(r"^[A-Za-z0-9+/=]+$", value):
            try:
                decoded = b64decode(value).decode("utf-8")
                json_data = loads(decoded)
                if isinstance(json_data, dict):
                    credential_items = {
                        k.lower(): str(v).removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                        for k, v in json_data.items()
                    }
            except BaseException:
                LOGGER.debug(format_exc())

    # Process base64 encoded credentials (except for rfc2136)
    if decode_base64 and credential_items:
        for key, value in credential_items.items():
            if authenticator != "rfc2136" and len(value) % 4 == 0 and match(r"^[A-Za-z0-9+/=]+$", value):
                try:
                    decoded = b64decode(value).decode("utf-8")
                    if decoded != value:
                        credential_items[key] = decoded.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                except BaseException:
                    LOGGER.debug(format_exc())

    if not credential_items:
        LOGGER.warning(f"[Service: {service}] DNS challenge selected but no DNS credentials are configured, skipping generation.")
        return None

    try:
        return PROVIDERS[authenticator](**credential_items)
    except ValidationError as ve:
        LOGGER.debug(format_exc())
        LOGGER.error(f"[Service: {service}] Error while validating credentials, skipping generation: {ve}")
        return None


def build_service_config(service: str) -> Tuple[List[str], Dict[str, Union[str, bool, int, Dict[str, str]]]]:
    def env(key: str, default: Optional[str] = None) -> str:
        if IS_MULTISITE:
            return getenv(f"{service}_{key}", default)
        return getenv(key, default)

    authenticator = env("LETS_ENCRYPT_DNS_PROVIDER", "").lower()
    server_names_val = env("SERVER_NAME", "www.example.com").strip() if IS_MULTISITE else getenv("SERVER_NAME", "www.example.com").strip()
    email_val = env("EMAIL_LETS_ENCRYPT", "").strip()
    retries_val = env("LETS_ENCRYPT_MAX_RETRIES", "0")
    challenge_val = env("LETS_ENCRYPT_CHALLENGE", "http").lower()
    profile_val = env("LETS_ENCRYPT_PROFILE", "classic").lower()
    custom_profile = env("LETS_ENCRYPT_CUSTOM_PROFILE", "").lower()
    dns_propagation_val = env("LETS_ENCRYPT_DNS_PROPAGATION", DNS_PROPAGATION_DEFAULT).lower()
    decode_base64 = env("LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64", "yes").lower() == "yes"
    wildcard = env("USE_LETS_ENCRYPT_WILDCARD", "no").lower() == "yes"
    activated = env("AUTO_LETS_ENCRYPT", "no").lower() == "yes" and env("LETS_ENCRYPT_PASSTHROUGH", "no").lower() == "no"

    # User-friendly checks
    if activated and not server_names_val:
        LOGGER.warning(f"[Service: {service}] SERVER_NAME is empty. Please set a valid server name, skipping generation.")
        activated = False

    if email_val:
        if "@" not in email_val:
            if activated:
                LOGGER.warning(f"[Service: {service}] EMAIL_LETS_ENCRYPT is invalid. Ignoring the provided value and proceeding without a contact email.")
            email_val = ""
    elif activated:
        LOGGER.warning(f"[Service: {service}] EMAIL_LETS_ENCRYPT is not set. Proceeding without a contact email.")

    try:
        retries_int = int(retries_val)
        if retries_int < 0:
            if activated:
                LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_MAX_RETRIES is negative. Defaulting to 0.")
            retries_int = 0
    except Exception:
        if activated:
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_MAX_RETRIES is not a valid integer. Defaulting to 0.")
        retries_int = 0

    if activated and challenge_val not in CHALLENGE_TYPES:
        LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_CHALLENGE '{challenge_val}' is invalid. Must be one of {CHALLENGE_TYPES!r}, skipping generation.")
        activated = False

    if custom_profile:
        profile_val = custom_profile
    elif profile_val not in PROFILE_TYPES:
        if activated:
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_PROFILE '{profile_val}' is invalid. Must be one of {PROFILE_TYPES!r}. Defaulting to 'classic'.")
        profile_val = "classic"

    # Validate dns_propagation
    if dns_propagation_val != DNS_PROPAGATION_DEFAULT:
        try:
            dns_propagation_int = int(dns_propagation_val)
            if dns_propagation_int <= 0:
                if activated:
                    LOGGER.warning(
                        f"[Service: {service}] LETS_ENCRYPT_DNS_PROPAGATION must be a positive integer or '{DNS_PROPAGATION_DEFAULT}'. Defaulting to '{DNS_PROPAGATION_DEFAULT}'."
                    )
                dns_propagation_val = DNS_PROPAGATION_DEFAULT
        except Exception:
            if activated:
                LOGGER.warning(
                    f"[Service: {service}] LETS_ENCRYPT_DNS_PROPAGATION is not a valid integer or '{DNS_PROPAGATION_DEFAULT}'. Defaulting to '{DNS_PROPAGATION_DEFAULT}'."
                )
            dns_propagation_val = DNS_PROPAGATION_DEFAULT

    provider = None
    if challenge_val == "dns":
        if not authenticator:
            if activated:
                LOGGER.warning(f"[Service: {service}] DNS challenge selected but no DNS provider is configured, skipping generation.")
            activated = False
        elif authenticator not in PROVIDERS:
            if activated:
                LOGGER.warning(
                    f"[Service: {service}] DNS provider '{authenticator}' is not supported. Must be one of {list(PROVIDERS.keys())!r}, skipping generation."
                )
            activated = False
        else:
            provider = extract_provider(service, authenticator, decode_base64)
            if not provider:
                activated = False
    else:
        authenticator = "manual"
        if wildcard:
            LOGGER.debug(f"[Service: {service}] Wildcard domains are not supported for HTTP challenges, deactivating wildcard support.")
            wildcard = False

    server_names = server_names_val.split()

    return server_names, {
        "server_names": "",
        "activated": activated,
        "email": email_val,
        "challenge": challenge_val,
        "authenticator": authenticator or "manual",
        "dns_propagation": dns_propagation_val,
        "provider": provider,
        "wildcard": wildcard,
        "staging": env("USE_LETS_ENCRYPT_STAGING", "no").lower() == "yes",
        "profile": profile_val,
        "disable_psl_check": env("LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", "no").lower() == "yes",
        "retries": retries_int,
        "exists": False,
        "force_renew": False,
    }


def extract_wildcard_groups(domains: List[str]) -> Dict[str, List[str]]:
    cleaned_labels: List[List[str]] = []

    for domain in domains:
        cleaned = domain.strip().removeprefix("*.").lower()
        if not cleaned:
            continue
        labels = [part for part in cleaned.split(".") if part]
        if labels:
            cleaned_labels.append(labels)

    if not cleaned_labels:
        return []

    grouped: Dict[str, List[List[str]]] = defaultdict(list)
    for labels in cleaned_labels:
        key = ".".join(labels[-2:]) if len(labels) >= 2 else ".".join(labels)
        grouped[key].append(labels)

    groups: Dict[str, Set[str]] = {}
    for labels_list in grouped.values():
        for base in _determine_wildcard_bases(labels_list):
            base = base.strip(".")
            if not base:
                continue
            groups.setdefault(base, set()).update({f"*.{base}", base})

    return {base: sorted(names, key=lambda value: (0 if value.startswith("*.") else 1, value)) for base, names in groups.items()}


def certificate_fingerprint(config: Dict[str, Union[str, bool, int, Dict[str, str]]]) -> Tuple:
    provider_hash = ""
    if config.get("challenge") == "dns" and config.get("provider"):
        provider_hash = bytes_hash(config["provider"].get_formatted_credentials(), algorithm="sha256")
    return (
        config.get("challenge"),
        config.get("authenticator"),
        config.get("staging"),
        config.get("profile"),
        config.get("email"),
        config.get("dns_propagation"),
        config.get("wildcard"),
        config.get("disable_psl_check"),
        provider_hash,
    )


def build_service_entries(service: str) -> Dict[str, Dict[str, Union[str, bool, int, Dict[str, str]]]]:
    server_names, base_config = build_service_config(service)
    if not server_names:
        return {}

    entries: Dict[str, Dict[str, Union[str, bool, int, Dict[str, str]]]] = {}
    if base_config["wildcard"]:
        wildcard_groups = extract_wildcard_groups(server_names)
        if not wildcard_groups and base_config["activated"]:
            LOGGER.warning(f"[Service: {service}] No valid wildcard groups found, skipping generation.")
        for base, names in wildcard_groups.items():
            config = base_config.copy()
            config["server_names"] = ",".join(names)
            entries[base] = config
        return entries

    config = base_config.copy()
    config["server_names"] = ",".join(server_names)
    entries[service] = config
    return entries


def _determine_wildcard_bases(labels_list: List[List[str]]) -> Set[str]:
    if not labels_list:
        return set()

    if len(labels_list) == 1:
        labels = labels_list[0]
        if len(labels) > 2:
            return {".".join(labels[1:])}
        return {".".join(labels)}

    min_len = min(len(labels) for labels in labels_list)
    common_suffix: List[str] = []

    for idx in range(1, min_len + 1):
        label = labels_list[0][-idx]
        if all(labels[-idx] == label for labels in labels_list):
            common_suffix.insert(0, label)
        else:
            break

    if len(common_suffix) >= 2 and len(common_suffix) >= (min_len - 1):
        return {".".join(common_suffix)}

    bases: Set[str] = set()
    for labels in labels_list:
        if len(labels) > 2:
            bases.add(".".join(labels[1:]))
        else:
            bases.add(".".join(labels))

    return bases


def certbot_delete(service: str, cmd_env: Dict[str, str] = None) -> int:
    # * Building the certbot command
    command = [
        CERTBOT_BIN,
        "delete",
        "-n",
        "--cert-name",
        service,
        "--config-dir",
        DATA_PATH.as_posix(),
        "--work-dir",
        WORK_DIR,
        "--logs-dir",
        LOGS_DIR,
    ]

    if LOG_LEVEL == "DEBUG":
        command.append("-v")

    if not cmd_env:
        cmd_env = {}

    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=cmd_env)

    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 2)
            if rlist:
                for line in process.stderr:
                    LOGGER_CERTBOT.info(line.strip())
                    break

    return process.returncode


def certbot_new(
    service: str,
    config: Dict[str, Union[str, bool, int, Dict[str, str]]],
    cmd_env: Dict[str, str],
    paths: CertbotPaths,
) -> int:
    # * Building the certbot command
    command = [
        CERTBOT_BIN,
        "certonly",
        "-n",
        "--cert-name",
        service,
        "-d",
        config["server_names"],
        "--preferred-profile",
        config["profile"],
        "--agree-tos",
        "--config-dir",
        paths.config_dir.as_posix(),
        "--work-dir",
        paths.work_dir.as_posix(),
        "--logs-dir",
        paths.logs_dir.as_posix(),
        "--break-my-certs",
        "--expand",
    ]

    if config.get("email"):
        command.extend(["--email", config["email"]])
    else:
        command.append("--register-unsafely-without-email")

    account_id = select_account_id(paths.config_dir.joinpath("accounts"), bool(config["staging"]), str(config.get("email") or ""))
    if account_id:
        command.extend(["--account", account_id])

    if LOG_LEVEL == "DEBUG":
        command.append("-v")

    if config["challenge"] == "dns":
        # * Adding DNS challenge hooks
        command.append("--preferred-challenges=dns")

        # * Adding the propagation time to the command
        if config["dns_propagation"] != DNS_PROPAGATION_DEFAULT:
            command.extend([f"--dns-{config['authenticator']}-propagation-seconds", str(config["dns_propagation"])])

        # * Caching the credentials file if not already done
        credentials = config["provider"].get_formatted_credentials()
        credentials_file = f"credentials_{bytes_hash(credentials, algorithm='sha256')[:12]}.{config['provider'].get_file_type()}"
        credentials_path = CACHE_PATH.joinpath(credentials_file)
        if not credentials_path.is_file() or config["force_renew"]:
            JOB.cache_file(credentials_file, credentials)
        credentials_path.chmod(0o600)  # Set permissions to read/write for owner only

        # * Adding the credentials to the command
        if config["authenticator"] == "route53":
            cmd_env["AWS_CONFIG_FILE"] = credentials_path.as_posix()
        else:
            command.extend([f"--dns-{config['authenticator']}-credentials", credentials_path.as_posix()])

        command.extend(config["provider"].get_extra_args())
    else:
        # * Adding HTTP challenge hooks
        command.extend(
            [
                "--manual",
                "--preferred-challenges=http",
                "--manual-auth-hook",
                JOBS_PATH.joinpath("certbot-auth.py").as_posix(),
                "--manual-cleanup-hook",
                JOBS_PATH.joinpath("certbot-cleanup.py").as_posix(),
            ]
        )

    if config["staging"]:
        command.append("--staging")

    if config["force_renew"]:
        renewal_file = DATA_PATH.joinpath("renewal", f"{service}.conf")
        if renewal_file.is_file():
            ret = certbot_delete(service, cmd_env)
            if ret != 0:
                LOGGER.error(f"Failed to delete certificate for {service}")
        else:
            LOGGER.info(f"No existing certificate found for {service}, skipping removal.")

    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=cmd_env)

    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 2)
            if rlist:
                for line in process.stderr:
                    LOGGER_CERTBOT.info(line.strip())
                    break

    return process.returncode


def generate_certificate(service: str, config: Dict[str, Union[str, bool, int, Dict[str, str]]], cmd_env: Dict[str, str]) -> bool:
    LOGGER.info(
        f"Asking{' wildcard' if config['wildcard'] else ''} certificates for domain(s) : {config['server_names']} (email = {config['email'] or 'not provided'}){' using staging' if config['staging'] else ''} with {config['challenge']} challenge, using {config['profile']!r} profile..."
    )
    LOGGER.debug(f"Service configuration: {config}")

    concurrent_requests = getenv("LETS_ENCRYPT_CONCURRENT_REQUESTS", "no").lower() == "yes"
    paths, temp_root = prepare_certbot_paths(service, concurrent_requests, CACHE_PATH, DATA_PATH, WORK_DIR, LOGS_DIR)
    success = False

    try:
        for attempts in range(1, config["retries"] + 2):
            if attempts > 1:
                LOGGER.warning(f"Certificate generation failed, retrying... (attempt {attempts}/{config['retries'] + 1})")
                # Wait before retrying (exponential backoff: 30s, 60s, 120s...)
                wait_time = min(30 * (2 ** (attempts - 2)), 300)  # Cap at 5 minutes
                LOGGER.info(f"Waiting {wait_time} seconds before retry...")
                sleep(wait_time)

            with RUNNING_LOCK:
                global RUNNING_CERTBOT
                RUNNING_CERTBOT += 1
            try:
                ret = certbot_new(service, config, cmd_env.copy(), paths)
            finally:
                with RUNNING_LOCK:
                    RUNNING_CERTBOT -= 1

            if ret == 0:
                LOGGER.info(f"Certificate(s) for {service} generated successfully.")
                success = True
                return True
    finally:
        finalize_certbot_run(paths, temp_root, success, MERGE_LOCK, DATA_PATH, WORK_DIR, LOGS_DIR, LOGGER)

    LOGGER.error(f"Failed to generate certificate(s) for {service} after {config['retries'] + 1} attempts.")
    return False


try:
    # ? Load services configuration
    server_names = getenv("SERVER_NAME", "www.example.com").strip()

    if not server_names:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = {}
    for service in server_names.split():
        if not service.strip():
            continue

        for cert_name, config in build_service_entries(service).items():
            if cert_name in services:
                if certificate_fingerprint(services[cert_name]) == certificate_fingerprint(config):
                    merged = normalize_server_names(services[cert_name]["server_names"]) | normalize_server_names(config["server_names"])
                    services[cert_name]["server_names"] = format_server_names(merged)
                    continue
                LOGGER.warning(f"[Service: {cert_name}] Certificate configuration conflict detected, keeping first occurrence.")
                continue
            services[cert_name] = config

    if not any(service["activated"] for service in services.values()):
        LOGGER.info("No services uses Let's Encrypt, skipping generation of new certificates...")
        sys_exit(0)

    prepare_logs_dir()

    JOB = Job(LOGGER, __file__.replace("new", "renew"))

    # ? Fetch existing certificates
    cmd_env = environ.copy()

    db_config = JOB.db.get_config()
    for key in db_config:
        if key in cmd_env:
            del cmd_env[key]

    cmd_env["PYTHONPATH"] = cmd_env["PYTHONPATH"] + (f":{DEPS_PATH}" if DEPS_PATH not in cmd_env["PYTHONPATH"] else "")
    if getenv("DATABASE_URI", ""):
        cmd_env["DATABASE_URI"] = getenv("DATABASE_URI", "")

    proc = run(
        [
            CERTBOT_BIN,
            "certificates",
            "-n",
            "--config-dir",
            DATA_PATH.as_posix(),
            "--work-dir",
            WORK_DIR,
            "--logs-dir",
            LOGS_DIR,
        ],
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        env=cmd_env,
        check=False,
    )
    stdout = proc.stdout
    existing_certificates = {}

    LOGGER_CERTBOT.debug(f"Certbot output:\n{stdout}")

    # ? Check if the command was successful
    if proc.returncode != 0:
        LOGGER.error(f"Failed to fetch existing certificates, force the generation of certificates: \n{stdout}")
        services = {service: config | {"force_renew": True} for service, config in services.items()}
    else:
        # ? Parse existing certificates
        for certificate_block in stdout.split("Certificate Name: ")[1:]:
            certificate_lines = certificate_block.splitlines()
            if not certificate_lines:
                continue

            service = certificate_lines[0].split()[0].strip()
            domains = parse_certbot_domains(certificate_block)

            existing_certificates[service] = {"active": False, "server_names": domains, "server_names_set": normalize_server_names(domains)}

            renewal_file = DATA_PATH.joinpath("renewal", f"{service}.conf")
            if renewal_file.is_file():
                renewal_content = renewal_file.read_text()

                match_profile = search(r"^preferred_profile\s*=\s*(\S+)$", renewal_content, MULTILINE)
                profile = match_profile.group(1) if match_profile else ""

                match_challenge = search(r"^pref_challs\s*=\s*(\S+)$", renewal_content, MULTILINE)
                challenge = match_challenge.group(1).split(",")[0].replace("-01", "") if match_challenge else ""

                match_authenticator = search(r"^authenticator\s*=\s*(\S+)$", renewal_content, MULTILINE)
                authenticator = match_authenticator.group(1).replace("dns-", "") if match_authenticator else ""

                match_credentials = search(rf"^dns_{authenticator}_credentials\s*=\s*(\S+)$", renewal_content, MULTILINE)
                credentials_hash = ""
                if match_credentials and match_credentials.group(1):
                    credentials_path = Path(match_credentials.group(1))
                    if credentials_path.is_file():
                        credentials_hash = file_hash(credentials_path, algorithm="sha256")

                match_server = search(r"^server\s*=\s*(\S+)$", renewal_content, MULTILINE)
                server = match_server.group(1) if match_server else ""

                existing_certificates[service].update(
                    {
                        "challenge": challenge,
                        "authenticator": authenticator,
                        "credentials_hash": credentials_hash,
                        "staging": "acme-staging" in server,
                        "profile": profile,
                    }
                )

        LOGGER_CERTBOT.debug(f"Existing certificates: {existing_certificates}")

    # ? Check if the services' certificates already exist
    for server_name, config in services.items():
        if config["force_renew"] or not config["activated"] or server_name not in existing_certificates:
            continue

        existing_cert = existing_certificates[server_name]
        existing_cert["active"] = True

        if not config["disable_psl_check"]:
            if psl_lines is None:
                psl_lines = load_public_suffix_list(JOB)
            if psl_rules is None:
                psl_rules = parse_psl(psl_lines)

            if check_psl_blacklist(list(normalize_server_names(config["server_names"])), psl_rules, server_name):
                config["activated"] = False
                continue

        config_server_names = normalize_server_names(config["server_names"])
        existing_server_names = existing_cert["server_names_set"]
        wildcard_valid = config["wildcard"] and config["challenge"] == "dns"

        if not wildcard_valid:
            config_server_names = filter_wildcard_names(config_server_names)
            existing_server_names = filter_wildcard_names(existing_server_names)

        if config_server_names != existing_server_names:
            LOGGER.warning(f"[Service: {server_name}] Server names do not match existing certificate, forcing renewal.")
            config["force_renew"] = True
        elif config["challenge"] != existing_cert["challenge"]:
            LOGGER.warning(f"[Service: {server_name}] Challenge type does not match existing certificate, forcing renewal.")
            config["force_renew"] = True
        elif config["authenticator"] != existing_cert["authenticator"]:
            LOGGER.warning(f"[Service: {server_name}] DNS provider does not match existing certificate, forcing renewal.")
            config["force_renew"] = True
        elif config["staging"] != existing_cert["staging"]:
            LOGGER.warning(f"[Service: {server_name}] Staging environment does not match existing certificate, forcing renewal.")
            config["force_renew"] = True
        elif config["profile"] != existing_cert["profile"]:
            LOGGER.warning(f"[Service: {server_name}] Profile does not match existing certificate, forcing renewal.")
            config["force_renew"] = True

        if config["challenge"] == "dns" and bytes_hash(config["provider"].get_formatted_credentials(), algorithm="sha256") != existing_cert["credentials_hash"]:
            LOGGER.warning(f"[Service: {server_name}] DNS credentials have changed, forcing renewal.")
            config["force_renew"] = True

    # ? generate new certificates and renew existing ones if needed
    concurrent_requests = getenv("LETS_ENCRYPT_CONCURRENT_REQUESTS", "no").lower() == "yes"
    pending_services: List[Tuple[str, Dict[str, Union[str, bool, int, Dict[str, str]]]]] = []

    for service, config in services.items():
        if existing_certificates.get(service, {}).get("active") and not config["force_renew"]:
            LOGGER.info(f"Certificate(s) for {service} already exist, skipping generation.")
            config["exists"] = True
            continue
        if not config["activated"]:
            continue
        pending_services.append((service, config))

    if pending_services:
        if concurrent_requests:
            required_accounts: Set[Tuple[bool, str]] = set()
            for _, config in pending_services:
                required_accounts.add((bool(config.get("staging")), str(config.get("email") or "")))
            ensure_accounts(required_accounts, cmd_env.copy(), CERTBOT_BIN, LOG_LEVEL, DATA_PATH, WORK_DIR, LOGS_DIR, LOGGER)
        start_progress_monitor()
        try:
            if concurrent_requests and len(pending_services) > 1:
                max_workers = max(1, min(len(pending_services), effective_cpu_count()))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(generate_certificate, service, config, cmd_env.copy()): service for service, config in pending_services}
                    for future in as_completed(futures):
                        service = futures[future]
                        config = services[service]
                        try:
                            success = future.result()
                        except BaseException as e:
                            LOGGER.error(f"Unexpected error while generating certificate(s) for {service}: {e}")
                            success = False
                        config["exists"] = success
                        if success:
                            status = 1 if status == 0 else status
                        else:
                            status = 2
            else:
                for service, config in pending_services:
                    config["exists"] = generate_certificate(service, config, cmd_env)
                    if config["exists"]:
                        status = 1 if status == 0 else status
                    else:
                        status = 2
        finally:
            stop_progress_monitor()

    if CACHE_PATH.is_dir():
        # * Clean up unused credential files
        used_credential_files = set()
        for config in services.values():
            if config.get("exists") and config.get("challenge") == "dns" and config.get("provider"):
                used_credential_files.add(
                    f"credentials_{bytes_hash(config['provider'].get_formatted_credentials(), algorithm='sha256')[:12]}.{config['provider'].get_file_type()}"
                )

        for ext in ("*.ini", "*.env", "*.json"):
            for file in CACHE_PATH.glob(ext):
                if file.name not in used_credential_files:
                    JOB.del_cache(file.name)
                    LOGGER.debug(f"Removed unused credential file: {file.name}")

        # * Clearing all no longer needed certificates
        if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
            for service, data in existing_certificates.items():
                if not data["active"]:
                    LOGGER.warning(f"Certificate for {service} does not exist anymore, removing...")

                    ret = certbot_delete(service, cmd_env)

                    if ret != 0:
                        LOGGER.error(f"Failed to delete certificate for {service}")
                    else:
                        LOGGER.info(f"Certificate for {service} deleted successfully.")

        # * Save data to db cache
        if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
            cached, err = JOB.cache_dir(DATA_PATH)
            if not cached:
                LOGGER.error(f"Error while saving data to db cache : {err}")
            else:
                LOGGER.info("Successfully saved data to db cache")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-new.py :\n{e}")

sys_exit(status)
