#!/usr/bin/env python3

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from ipaddress import ip_address
from json import dumps, loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, search
from subprocess import DEVNULL, PIPE, STDOUT, Popen, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from threading import Event, Lock, Thread
from traceback import format_exc
from typing import Dict, List, Optional, Set, Tuple, Union
from certbot_concurrency import (
    CertbotPaths,
    ensure_accounts,
    ensure_accounts_for_orphans,
    ensure_zerossl_accounts,
    finalize_certbot_run,
    prepare_certbot_paths,
    select_account_id,
)

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from common_utils import bytes_hash, effective_cpu_count, file_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

from letsencrypt_utils import (
    CERTBOT_BIN,
    DEPS_PATH,
    LETSENCRYPT_CACHE_PATH as CACHE_PATH,
    LETSENCRYPT_DATA_PATH as DATA_PATH,
    LETSENCRYPT_JOBS_PATH as JOBS_PATH,
    LETSENCRYPT_LOGS_DIR as LOGS_DIR,
    LETSENCRYPT_WORK_DIR as WORK_DIR,
    PROVIDERS,
    certbot_log_backup_flags,
    ZEROSSL_BOT_SCRIPT,
    attach_job_log_file,
    build_certbot_env,
    extract_provider,
    get_expected_acme_directory,
    is_stale_account_line,
    le_cache_write_lock,
    letsencrypt_cache_consistent,
    prepare_logs_dir,
    purge_lineage,
    purge_stale_account,
    resolve_certbot_entrypoint,
    sanitize_and_persist,
    stream_certbot,
)

LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper()
LOGGER = getLogger("LETS-ENCRYPT.NEW")
LOGGER_CERTBOT = getLogger("LETS-ENCRYPT.NEW.CERTBOT")

# Attach before any service is inspected: the "skipping generation" warnings that used to
# be visible only in `docker logs` are emitted while building the per-service config.
attach_job_log_file(LOGGER, "certbot-new.log", LOGS_DIR)

ZEROSSL_API_KEY_HASHES_PATH = DATA_PATH.joinpath("renewal", ".bw-zerossl-api-key-hashes.json")
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


IS_MULTISITE = getenv("MULTISITE", "no") == "yes"
CHALLENGE_TYPES = ("http", "dns")
PROFILE_TYPES = ("classic", "tlsserver", "shortlived")
ACME_SERVER_TYPES = ("letsencrypt", "zerossl")
DNS_PROPAGATION_DEFAULT = "default"
CERTBOT_TIMEOUT = 900  # 15 minutes max for a single certbot invocation

# Set from certbot_new(), which can run in a thread pool, so the recovery below the generation loop
# knows a purge happened without threading a return value back through the executor.
STALE_ACCOUNT_PURGED = Event()


def normalize_server_names(server_names: str) -> Set[str]:
    """Return a normalized set of server names split on comma/space, lowercased and trimmed."""
    return {part.strip().lower() for part in server_names.replace(",", " ").split() if part.strip()}


def unissuable_names(names: List[str]) -> List[str]:
    """Return the names no public ACME CA can issue for: IP literals and single-label hosts.

    Nothing else rejects them, so they reach certbot, fail on every run and keep the whole job
    red even when every other service got its certificate.
    """
    unissuable = []
    for name in names:
        candidate = name.strip().lower().removeprefix("*.")
        try:
            ip_address(candidate)
        except ValueError:
            if "." not in candidate.rstrip("."):
                unissuable.append(name)
        else:
            unissuable.append(name)
    return unissuable


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


def normalize_server_url(url: str) -> str:
    return url.strip().rstrip("/")


def load_zerossl_api_key_hashes() -> Dict[str, str]:
    if not ZEROSSL_API_KEY_HASHES_PATH.is_file():
        return {}

    try:
        data = loads(ZEROSSL_API_KEY_HASHES_PATH.read_text())
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}
    except BaseException as e:
        LOGGER.warning(f"Failed to read ZeroSSL API key hash file {ZEROSSL_API_KEY_HASHES_PATH}: {e}")
        return {}


def save_zerossl_api_key_hashes(hashes: Dict[str, str]) -> None:
    try:
        ZEROSSL_API_KEY_HASHES_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not hashes:
            ZEROSSL_API_KEY_HASHES_PATH.unlink(missing_ok=True)
            return
        ZEROSSL_API_KEY_HASHES_PATH.write_text(dumps(hashes, sort_keys=True))
    except BaseException as e:
        LOGGER.warning(f"Failed to persist ZeroSSL API key hashes to {ZEROSSL_API_KEY_HASHES_PATH}: {e}")


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


def build_service_config(service: str) -> Tuple[List[str], Dict[str, Union[str, bool, int, Dict[str, str]]]]:
    def env(key: str, default: Optional[str] = None) -> str:
        if IS_MULTISITE:
            return getenv(f"{service}_{key}", default)
        return getenv(key, default)

    authenticator = env("LETS_ENCRYPT_DNS_PROVIDER", "").lower()
    acme_server = env("LETS_ENCRYPT_SERVER", "letsencrypt").lower()
    zerossl_api_key = env("LETS_ENCRYPT_ZEROSSL_API_KEY", "").strip()
    zerossl_api_retry_val = env("LETS_ENCRYPT_ZEROSSL_API_RETRY", "3").strip()
    zerossl_api_retry_delay_val = env("LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY", "2").strip()
    zerossl_api_connect_timeout_val = env("LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT", "5").strip()
    zerossl_api_max_time_val = env("LETS_ENCRYPT_ZEROSSL_API_MAX_TIME", "20").strip()
    zerossl_api_key_hash = bytes_hash(zerossl_api_key.encode("utf-8"), algorithm="sha256") if zerossl_api_key else ""
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
    staging = env("USE_LETS_ENCRYPT_STAGING", "no").lower() == "yes"
    # Set when the service asked for a certificate but its configuration makes issuance
    # impossible. Distinguishes "not using Let's Encrypt" (a green job) from "wants a
    # certificate and cannot get one" (a red job the operator has to look at). Settings
    # that merely fall back to a default are not misconfigurations.
    misconfigured = False

    if acme_server not in ACME_SERVER_TYPES:
        if activated:
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_SERVER '{acme_server}' is invalid. Defaulting to 'letsencrypt'.")
        acme_server = "letsencrypt"

    # User-friendly checks
    if activated and not server_names_val:
        LOGGER.warning(f"[Service: {service}] SERVER_NAME is empty. Please set a valid server name, skipping generation.")
        misconfigured = True
        activated = False

    if email_val:
        if "@" not in email_val:
            if activated:
                LOGGER.warning(f"[Service: {service}] EMAIL_LETS_ENCRYPT is invalid. Ignoring the provided value and proceeding without a contact email.")
            email_val = ""
    elif activated:
        LOGGER.warning(f"[Service: {service}] EMAIL_LETS_ENCRYPT is not set. Proceeding without a contact email.")

    if acme_server == "zerossl" and not email_val and not zerossl_api_key and activated:
        LOGGER.warning(f"[Service: {service}] ZeroSSL requires EMAIL_LETS_ENCRYPT or LETS_ENCRYPT_ZEROSSL_API_KEY. Skipping generation.")
        misconfigured = True
        activated = False

    if acme_server == "zerossl" and staging:
        if activated:
            LOGGER.warning(f"[Service: {service}] USE_LETS_ENCRYPT_STAGING is ignored when LETS_ENCRYPT_SERVER is set to 'zerossl'.")
        staging = False

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

    try:
        zerossl_api_retry_int = int(zerossl_api_retry_val)
        if zerossl_api_retry_int < 0:
            raise ValueError("negative")
    except Exception:
        if activated and acme_server == "zerossl":
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_ZEROSSL_API_RETRY must be >= 0. Defaulting to 3.")
        zerossl_api_retry_int = 3

    try:
        zerossl_api_retry_delay_int = int(zerossl_api_retry_delay_val)
        if zerossl_api_retry_delay_int < 0:
            raise ValueError("negative")
    except Exception:
        if activated and acme_server == "zerossl":
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY must be >= 0. Defaulting to 2.")
        zerossl_api_retry_delay_int = 2

    try:
        zerossl_api_connect_timeout_int = int(zerossl_api_connect_timeout_val)
        if zerossl_api_connect_timeout_int <= 0:
            raise ValueError("non-positive")
    except Exception:
        if activated and acme_server == "zerossl":
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT must be > 0. Defaulting to 5.")
        zerossl_api_connect_timeout_int = 5

    try:
        zerossl_api_max_time_int = int(zerossl_api_max_time_val)
        if zerossl_api_max_time_int <= 0:
            raise ValueError("non-positive")
    except Exception:
        if activated and acme_server == "zerossl":
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_ZEROSSL_API_MAX_TIME must be > 0. Defaulting to 20.")
        zerossl_api_max_time_int = 20

    if activated and challenge_val not in CHALLENGE_TYPES:
        LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_CHALLENGE '{challenge_val}' is invalid. Must be one of {CHALLENGE_TYPES!r}, skipping generation.")
        misconfigured = True
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
            misconfigured = misconfigured or activated
            activated = False
        elif authenticator not in PROVIDERS:
            if activated:
                LOGGER.warning(
                    f"[Service: {service}] DNS provider '{authenticator}' is not supported. Must be one of {list(PROVIDERS.keys())!r}, skipping generation."
                )
            misconfigured = misconfigured or activated
            activated = False
        else:
            credential_key = f"{service}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" if IS_MULTISITE else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
            provider = extract_provider(service, credential_key, authenticator, decode_base64, LOGGER)
            if not provider:
                misconfigured = misconfigured or activated
                activated = False
    else:
        authenticator = "manual"
        if wildcard:
            LOGGER.debug(f"[Service: {service}] Wildcard domains are not supported for HTTP challenges, deactivating wildcard support.")
            wildcard = False

    server_names = server_names_val.split()

    unissuable = unissuable_names(server_names)
    if unissuable:
        issuable = [name for name in server_names if name not in unissuable]
        if activated:
            LOGGER.warning(
                f"[Service: {service}] No public CA issues certificates for {', '.join(unissuable)}"
                + (", requesting one for the remaining server names." if issuable else ", skipping generation.")
            )
        if issuable:
            server_names = issuable
        else:
            misconfigured = misconfigured or activated
            activated = False

    return server_names, {
        "server_names": "",
        "activated": activated,
        "misconfigured": misconfigured,
        "acme_server": acme_server,
        "acme_server_url": get_expected_acme_directory(acme_server, staging),
        "zerossl_api_key": zerossl_api_key,
        "zerossl_api_key_hash": zerossl_api_key_hash,
        "zerossl_api_retry": zerossl_api_retry_int,
        "zerossl_api_retry_delay": zerossl_api_retry_delay_int,
        "zerossl_api_connect_timeout": zerossl_api_connect_timeout_int,
        "zerossl_api_max_time": zerossl_api_max_time_int,
        "email": email_val,
        "challenge": challenge_val,
        "authenticator": authenticator or "manual",
        "dns_propagation": dns_propagation_val,
        "provider": provider,
        "wildcard": wildcard,
        "staging": staging,
        "profile": profile_val,
        "disable_psl_check": env("LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", "no").lower() == "yes",
        "retries": retries_int,
        "exists": False,
        "force_renew": False,
    }


def list_misconfigured(services: Dict[str, Dict[str, Union[str, bool, int, Dict[str, str]]]]) -> List[str]:
    """Names of services that asked for a certificate but cannot get one, sorted."""
    return sorted(name for name, config in services.items() if config.get("misconfigured"))


def extract_wildcard_groups(domains: List[str], service: str) -> Dict[str, List[str]]:
    cleaned_labels: List[List[str]] = []

    for domain in domains:
        cleaned = domain.strip().removeprefix("*.").lower()
        if not cleaned:
            continue
        labels = [part for part in cleaned.split(".") if part]
        if labels:
            cleaned_labels.append(labels)

    if not cleaned_labels:
        return {}

    grouped: Dict[str, List[List[str]]] = defaultdict(list)
    for labels in cleaned_labels:
        key = ".".join(labels[-2:]) if len(labels) >= 2 else ".".join(labels)
        grouped[key].append(labels)

    groups: Dict[str, Set[str]] = {}
    for labels_list in grouped.values():
        for base in _determine_wildcard_bases(labels_list, service):
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
        config.get("acme_server"),
        config.get("acme_server_url"),
        config.get("zerossl_api_key_hash"),
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

    # Deduplicate server names to avoid sending duplicate domains to the ACME server
    unique_names = normalize_server_names(",".join(server_names))
    if len(unique_names) < len(server_names):
        LOGGER.debug(f"[Service: {service}] Removed {len(server_names) - len(unique_names)} duplicate server name(s).")

    entries: Dict[str, Dict[str, Union[str, bool, int, Dict[str, str]]]] = {}
    if base_config["wildcard"]:
        wildcard_groups = extract_wildcard_groups(list(unique_names), service)
        if not wildcard_groups and base_config["activated"]:
            LOGGER.warning(f"[Service: {service}] No valid wildcard groups found, skipping generation.")
        for base, names in wildcard_groups.items():
            config = base_config.copy()
            config["server_names"] = ",".join(names)
            entries[base] = config
        return entries

    config = base_config.copy()
    config["server_names"] = format_server_names(unique_names)
    entries[service] = config
    return entries


def _determine_wildcard_bases(labels_list: List[List[str]], service: str) -> Set[str]:
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
        base = ".".join(common_suffix)
        # A wildcard matches exactly one label, so *.base plus base cover names of at most
        # len(common_suffix) + 1 labels. Anything deeper would be dropped from the certificate
        # while still being served, so refuse the whole group instead of issuing one that omits it.
        uncovered = sorted(".".join(labels) for labels in labels_list if len(labels) > len(common_suffix) + 1)
        if uncovered:
            covered = sorted(".".join(labels) for labels in labels_list if len(labels) <= len(common_suffix) + 1)
            LOGGER.error(
                f"[Service: {service}] Wildcard group *.{base} cannot cover {', '.join(uncovered)} alongside "
                f"{', '.join(covered)} "
                "(a wildcard matches a single label); skipping this group, nothing is issued for any of those "
                "names until they are split into separate services."
            )
            return set()
        return {base}

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
        *certbot_log_backup_flags(cmd_env),
    ]

    if LOG_LEVEL == "DEBUG":
        command.append("-v")

    if not cmd_env:
        cmd_env = {}

    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=cmd_env)

    if not stream_certbot(process, LOGGER_CERTBOT, CERTBOT_TIMEOUT):
        LOGGER.error(f"certbot delete for {service} timed out after {CERTBOT_TIMEOUT}s, killing process.")
        return 1

    return process.returncode


def certbot_new(
    service: str,
    config: Dict[str, Union[str, bool, int, Dict[str, str]]],
    cmd_env: Dict[str, str],
    paths: CertbotPaths,
) -> int:
    certbot_entrypoint = resolve_certbot_entrypoint(
        str(config.get("acme_server") or "letsencrypt"),
        CERTBOT_BIN,
        ZEROSSL_BOT_SCRIPT,
        LOGGER,
        cmd_env=cmd_env,
        fallback_to_certbot=False,
    )
    if not certbot_entrypoint:
        return 2

    # * Building the certbot command
    command = certbot_entrypoint + [
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
        *certbot_log_backup_flags(cmd_env),
        "--break-my-certs",
        "--expand",
    ]

    if config.get("email"):
        command.extend(["--email", config["email"]])
    else:
        command.append("--register-unsafely-without-email")

    # Always scope account lookup to the target ACME server's URL.
    # Without this, an LE account id can be passed as `--account` to a ZeroSSL
    # certbot certonly invocation (and vice versa) — certbot then constructs the
    # account directory from its own --server path and fails with AccountNotFound.
    acme_server_url = str(config.get("acme_server_url") or "")
    account_id = ""

    if config.get("acme_server") == "letsencrypt":
        account_id = select_account_id(
            paths.config_dir.joinpath("accounts"),
            bool(config["staging"]),
            str(config.get("email") or ""),
            server_url=acme_server_url,
        )
        if account_id:
            command.extend(["--account", account_id])
    else:
        cmd_env["LETS_ENCRYPT_ZEROSSL_API_RETRY"] = str(config.get("zerossl_api_retry") or 3)
        cmd_env["LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY"] = str(config.get("zerossl_api_retry_delay") or 2)
        cmd_env["LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT"] = str(config.get("zerossl_api_connect_timeout") or 5)
        cmd_env["LETS_ENCRYPT_ZEROSSL_API_MAX_TIME"] = str(config.get("zerossl_api_max_time") or 20)

        # Backward compatible env names consumed by zerossl-bot.
        cmd_env["ZEROSSL_API_RETRY"] = cmd_env["LETS_ENCRYPT_ZEROSSL_API_RETRY"]
        cmd_env["ZEROSSL_API_RETRY_DELAY"] = cmd_env["LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY"]
        cmd_env["ZEROSSL_API_CONNECT_TIMEOUT"] = cmd_env["LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT"]
        cmd_env["ZEROSSL_API_MAX_TIME"] = cmd_env["LETS_ENCRYPT_ZEROSSL_API_MAX_TIME"]

        zerossl_api_key = str(config.get("zerossl_api_key") or "")
        if zerossl_api_key:
            cmd_env["LETS_ENCRYPT_ZEROSSL_API_KEY"] = zerossl_api_key

        account_id = select_account_id(
            paths.config_dir.joinpath("accounts"),
            bool(config["staging"]),
            str(config.get("email") or ""),
            server_url=acme_server_url,
        )
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

    # Watch certbot output for a stale-account JWS rejection. When the ACME server
    # has pruned the account we hold on disk (common on LE staging), it answers
    # `Unable to validate JWS :: Account "<url>" not found`. certbot does NOT
    # re-register when `--account` is pinned, so every retry would reuse the dead
    # account and fail identically. Detect it, then drop the stale account dir so
    # the next attempt (select_account_id → None) registers a fresh account.
    stale_account = Event()

    def watch_stale_account(line: str) -> None:
        if is_stale_account_line(line):
            stale_account.set()

    if not stream_certbot(process, LOGGER_CERTBOT, CERTBOT_TIMEOUT, watch_stale_account):
        LOGGER.error(f"certbot for {service} timed out after {CERTBOT_TIMEOUT}s, killing process.")
        return 1

    if stale_account.is_set() and account_id:
        # Purge the canonical store, not paths.config_dir: in concurrent mode config_dir is a
        # throwaway scratch (merged only on success), so purging it leaves DATA_PATH untouched
        # and the stale account is restored next run. Non-concurrent: config_dir == DATA_PATH.
        if purge_stale_account(DATA_PATH, account_id, LOGGER):
            STALE_ACCOUNT_PURGED.set()

    return process.returncode


def generate_certificate(service: str, config: Dict[str, Union[str, bool, int, Dict[str, str]]], cmd_env: Dict[str, str]) -> bool:
    LOGGER.info(
        f"Asking{' wildcard' if config['wildcard'] else ''} certificates for domain(s) : {config['server_names']} (email = {config['email'] or 'not provided'}){' using staging' if config['staging'] else ''} with {config['challenge']} challenge, using {config['profile']!r} profile on {config['acme_server']}..."
    )
    debug_config = config.copy()
    if LOG_LEVEL != "TRACE" and debug_config.get("zerossl_api_key"):
        debug_config["zerossl_api_key"] = "***"
    LOGGER.debug(f"Service configuration: {debug_config}")

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
        misconfigured_services = list_misconfigured(services)
        if misconfigured_services:
            LOGGER.error(
                "Let's Encrypt is enabled but no certificate can be requested, invalid configuration for "
                f"{len(misconfigured_services)} service(s): {', '.join(misconfigured_services)}"
            )
            sys_exit(2)
        LOGGER.info("No services uses Let's Encrypt, skipping generation of new certificates...")
        sys_exit(0)

    # Still needed before certbot runs: sets the umask and sweeps unwritable log files.
    # The job's own log file is attached earlier, at import, without that side effect.
    prepare_logs_dir(LOGS_DIR, LOGGER)

    JOB = Job(LOGGER, __file__.replace("new", "renew"))

    # ? Fetch existing certificates
    cmd_env = build_certbot_env(JOB, DEPS_PATH)

    # Register an account for any CA whose renewal confs are orphaned and that has none left, so
    # the repoint inside sanitize_and_persist always has somewhere to point. Without it a purged
    # last account is terminal: issuance only registers as a side effect of `certbot certonly`,
    # which never runs while every certificate already exists.
    ensure_accounts_for_orphans(DATA_PATH, cmd_env.copy(), CERTBOT_BIN, LOG_LEVEL, WORK_DIR, LOGS_DIR, LOGGER)

    # Quarantine any renewal conf whose lineage name disagrees with its filename (or that has no
    # cert material) BEFORE calling certbot: a single broken conf makes `certbot certificates`
    # exit non-zero, which would otherwise force_renew every service and never persist the fix.
    sanitized_lineages = sanitize_and_persist(JOB, DATA_PATH, LOGGER)

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
            *certbot_log_backup_flags(cmd_env),
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
    listing_ok = proc.returncode == 0
    if not listing_ok:
        # Failing to list is a diagnostic failure, not proof the certificates are gone. Renewing
        # every service on that basis burns the ACME rate limits and repeats on every start, so
        # trust the lineages on disk instead and only issue for services that have none.
        LOGGER.error(f"Failed to fetch existing certificates, falling back to the certificates found on disk: \n{stdout}")
        for service in services:
            if DATA_PATH.joinpath("live", service, "fullchain.pem").is_file():
                existing_certificates[service] = {"active": False, "unparsed": True}
    else:
        # ? Parse existing certificates
        for certificate_block in stdout.split("Certificate Name: ")[1:]:
            certificate_lines = certificate_block.splitlines()
            if not certificate_lines:
                continue

            service = certificate_lines[0].split()[0].strip()
            domains = parse_certbot_domains(certificate_block)

            # Seed every key the comparison loop below reads unconditionally. They are only filled
            # in from the renewal conf, and a certificate certbot lists whose conf is missing would
            # otherwise raise KeyError there and end the job for every other service too.
            existing_certificates[service] = {
                "active": False,
                "server_names": domains,
                "server_names_set": normalize_server_names(domains),
                "challenge": "",
                "authenticator": "",
                "credentials_hash": "",
                "staging": False,
                "profile": "",
                "acme_server_url": "",
            }

            renewal_file = DATA_PATH.joinpath("renewal", f"{service}.conf")
            renewal_content = ""
            if renewal_file.is_file():
                # An unreadable or non-UTF-8 conf leaves the seeded defaults in place rather than
                # ending the job here, which would take every other service down with it.
                try:
                    renewal_content = renewal_file.read_text()
                except OSError as e:
                    LOGGER.error(f"Could not read the renewal conf for {service}, treating it as unknown: {e}")
                except UnicodeDecodeError:
                    LOGGER.error(f"The renewal conf for {service} is not valid UTF-8, treating it as unknown.")

            if renewal_content:
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
                        "acme_server_url": normalize_server_url(server),
                    }
                )

        LOGGER_CERTBOT.debug(f"Existing certificates: {existing_certificates}")

    zerossl_api_key_hashes = load_zerossl_api_key_hashes()
    LOGGER_CERTBOT.debug(f"Stored ZeroSSL API key hashes: {list(zerossl_api_key_hashes.keys())}")

    # ? Check if the services' certificates already exist
    for server_name, config in services.items():
        if config["force_renew"] or not config["activated"] or server_name not in existing_certificates:
            continue

        existing_cert = existing_certificates[server_name]
        existing_cert["active"] = True

        if existing_cert.get("unparsed"):
            # Nothing to compare the live certificate against, so leave it alone; certbot-renew
            # still picks it up on its daily run once it is close enough to expiry.
            continue

        if not config["disable_psl_check"]:
            if psl_lines is None:
                psl_lines = load_public_suffix_list(JOB)
            if psl_rules is None:
                psl_rules = parse_psl(psl_lines)

            if check_psl_blacklist(list(normalize_server_names(config["server_names"])), psl_rules, server_name):
                config["misconfigured"] = True
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
        elif normalize_server_url(str(config.get("acme_server_url") or "")) != normalize_server_url(str(existing_cert.get("acme_server_url") or "")):
            LOGGER.warning(f"[Service: {server_name}] ACME server does not match existing certificate, forcing renewal.")
            config["force_renew"] = True
        elif config.get("acme_server") == "zerossl":
            configured_api_key_hash = str(config.get("zerossl_api_key_hash") or "")
            previous_api_key_hash = str(zerossl_api_key_hashes.get(server_name, ""))
            if server_name in zerossl_api_key_hashes and configured_api_key_hash != previous_api_key_hash:
                LOGGER.warning(f"[Service: {server_name}] ZeroSSL API key changed, forcing renewal.")
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
            required_zerossl_accounts: Set[Tuple[bool, str]] = set()
            for _, config in pending_services:
                if config.get("acme_server") == "letsencrypt":
                    required_accounts.add((bool(config.get("staging")), str(config.get("email") or "")))
                else:
                    required_zerossl_accounts.add((bool(config.get("staging")), str(config.get("email") or "")))
            if required_accounts:
                ensure_accounts(required_accounts, cmd_env.copy(), CERTBOT_BIN, LOG_LEVEL, DATA_PATH, WORK_DIR, LOGS_DIR, LOGGER)
            if required_zerossl_accounts:
                zerossl_env = cmd_env.copy()
                zerossl_env["CERTBOT_BIN"] = CERTBOT_BIN
                # Collect ZeroSSL-specific env vars from any pending ZeroSSL service config
                for _, config in pending_services:
                    if config.get("acme_server") != "letsencrypt":
                        zerossl_api_key = str(config.get("zerossl_api_key") or "")
                        if zerossl_api_key:
                            zerossl_env["LETS_ENCRYPT_ZEROSSL_API_KEY"] = zerossl_api_key
                        zerossl_env["LETS_ENCRYPT_ZEROSSL_API_RETRY"] = str(config.get("zerossl_api_retry") or 3)
                        zerossl_env["LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY"] = str(config.get("zerossl_api_retry_delay") or 2)
                        zerossl_env["LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT"] = str(config.get("zerossl_api_connect_timeout") or 5)
                        zerossl_env["LETS_ENCRYPT_ZEROSSL_API_MAX_TIME"] = str(config.get("zerossl_api_max_time") or 20)
                        break
                ensure_zerossl_accounts(required_zerossl_accounts, zerossl_env, ZEROSSL_BOT_SCRIPT.as_posix(), LOG_LEVEL, DATA_PATH, WORK_DIR, LOGS_DIR, LOGGER)
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
                    # Same containment as the concurrent branch above: one service raising must not
                    # end the run for the ones after it, nor skip the cleanup and persist below.
                    try:
                        config["exists"] = generate_certificate(service, config, cmd_env)
                    except BaseException as e:
                        LOGGER.error(f"Unexpected error while generating certificate(s) for {service}: {e}")
                        config["exists"] = False
                    if config["exists"]:
                        status = 1 if status == 0 else status
                    else:
                        status = 2
        finally:
            stop_progress_monitor()

    # A purge during the loop above strands every renewal conf naming that account, and the persist
    # at the end refuses an inconsistent tree, so leaving the repair to the next run would never let
    # the purge reach the DB row: the dead account would come back with every restore.
    if STALE_ACCOUNT_PURGED.is_set():
        ensure_accounts_for_orphans(DATA_PATH, cmd_env.copy(), CERTBOT_BIN, LOG_LEVEL, WORK_DIR, LOGS_DIR, LOGGER)
        sanitized_lineages = sorted(set(sanitized_lineages) | set(sanitize_and_persist(JOB, DATA_PATH, LOGGER)))

    misconfigured_services = list_misconfigured(services)
    if misconfigured_services:
        LOGGER.error(
            f"Skipped certificate generation for {len(misconfigured_services)} service(s) with an invalid "
            f"Let's Encrypt configuration: {', '.join(misconfigured_services)}"
        )
        # Only escalate when nothing was generated. status 1 means certbot succeeded and the
        # scheduler still owes those certificates an nginx reload, which a status >= 2 would
        # suppress, leaving freshly issued certificates unserved.
        if status == 0:
            status = 2

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
        if not listing_ok:
            LOGGER.warning("Skipping the cleanup of old certificates: the certificate listing failed, so nothing can be declared unused.")
        elif getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
            for service, data in existing_certificates.items():
                if not data["active"]:
                    LOGGER.warning(f"Certificate for {service} does not exist anymore, removing...")

                    ret = certbot_delete(service, cmd_env)

                    if ret != 0:
                        # certbot delete fails on exactly the broken confs this cleanup exists to
                        # remove, so fall back to purging the lineage directly (conf + live/archive).
                        removed = purge_lineage(DATA_PATH, DATA_PATH.joinpath("renewal", f"{service}.conf"), quarantine_root=None, logger=LOGGER)
                        if removed:
                            LOGGER.info(f"certbot delete failed for {service}; purged {len(removed)} path(s) directly: {removed}")
                        else:
                            LOGGER.error(f"Failed to delete certificate for {service} and nothing was purged; manual cleanup may be required.")
                    else:
                        LOGGER.info(f"Certificate for {service} deleted successfully.")

        # * Persist ZeroSSL API key hash tracking (for change-triggered renewals)
        updated_zerossl_api_key_hashes = {key: value for key, value in zerossl_api_key_hashes.items() if key in services}
        for service, config in services.items():
            if config.get("acme_server") != "zerossl":
                updated_zerossl_api_key_hashes.pop(service, None)
                continue

            configured_hash = str(config.get("zerossl_api_key_hash") or "")
            # Only trust "exists" when the listing parsed: the on-disk fallback never got to
            # compare the API key, so recording it here would swallow a rotation for good.
            if config.get("exists") and listing_ok:
                updated_zerossl_api_key_hashes[service] = configured_hash
                continue

            # If generation failed but an old certificate is still active, keep previous hash
            # so the renewal attempt will be retried on the next run.
            if not existing_certificates.get(service, {}).get("active"):
                updated_zerossl_api_key_hashes.pop(service, None)

        save_zerossl_api_key_hashes(updated_zerossl_api_key_hashes)

        # * Save data to db cache
        # Guards: only re-cache if the initial restore succeeded AND we actually have
        # live certs on disk. Without these guards, a failed restore leaves DATA_PATH
        # empty (rmtree runs before extraction in Job.restore_cache) and a blind
        # cache_dir() call would overwrite the good DB row with empty state, losing
        # the certs from both disk and DB.
        if not JOB.restore_ok:
            LOGGER.error("Skipping db cache update: initial cache restore failed, refusing to overwrite good DB state with current disk state.")
            status = 2
        elif not sanitized_lineages and (not DATA_PATH.is_dir() or not any(DATA_PATH.glob("live/*/fullchain.pem"))):
            # Skip the "no live certs" persist only when nothing was sanitized; if a broken lineage
            # was quarantined we must still write the cleaned tree back so it can't be restored again.
            LOGGER.warning("Skipping db cache update: no live certificates found under DATA_PATH/live/*/fullchain.pem.")
        else:
            # Refuse to re-cache when renewal/ references account IDs that are missing from accounts/.
            # That snapshot would self-propagate certbot AccountNotFound errors across every renew.
            consistent, reason = letsencrypt_cache_consistent(DATA_PATH)
            if not consistent:
                LOGGER.error(
                    "Skipping db cache update to avoid persisting an inconsistent Let's Encrypt state "
                    f"({reason}). The DB cache row is left untouched. Renewals for the affected certificates fail until an "
                    "account exists for their CA; the next run repoints them automatically once one does."
                )
                # If certbot itself succeeded, the fresh certs are already on disk — signal a reload
                # (ret=1) so nginx picks them up. Persistence failure is logged separately above; do
                # not escalate to status=2 here, otherwise JobScheduler suppresses the reload.
                if status == 0:
                    status = 1
            else:
                # Serialize against the UI heal/delete flow, which writes the same DB cache row.
                with le_cache_write_lock():
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
