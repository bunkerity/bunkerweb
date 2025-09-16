#!/usr/bin/env python3

from base64 import b64decode
from datetime import datetime, timedelta
from json import loads
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, match, search
from select import select
from subprocess import DEVNULL, PIPE, STDOUT, Popen, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Dict, List, Optional, Tuple, Type, Union


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from pydantic import ValidationError
from requests import get

from common_utils import bytes_hash, file_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import setup_logger  # type: ignore

from letsencrypt_providers import (
    BunnyNetProvider,
    CloudflareProvider,
    DesecProvider,
    DigitalOceanProvider,
    DomainOffensiveProvider,
    DnsimpleProvider,
    DnsMadeEasyProvider,
    DynuProvider,
    GehirnProvider,
    GoogleProvider,
    InfomaniakProvider,
    IonosProvider,
    LinodeProvider,
    LuaDnsProvider,
    NjallaProvider,
    NSOneProvider,
    OvhProvider,
    Provider,
    Rfc2136Provider,
    Route53Provider,
    SakuraCloudProvider,
    ScalewayProvider,
)

LOG_LEVEL = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper()
LOGGER = setup_logger("LETS-ENCRYPT.new")
LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT.new.certbot")

CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")
PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

IS_MULTISITE = getenv("MULTISITE", "no") == "yes"
CHALLENGE_TYPES = ("http", "dns")
PROFILE_TYPES = ("classic", "tlsserver", "shortlived")
DNS_PROPAGATION_DEFAULT = "default"

PROVIDERS: Dict[str, Type[Provider]] = {
    "bunny": BunnyNetProvider,
    "cloudflare": CloudflareProvider,
    "desec": DesecProvider,
    "digitalocean": DigitalOceanProvider,
    "domainoffensive": DomainOffensiveProvider,
    "dnsimple": DnsimpleProvider,
    "dnsmadeeasy": DnsMadeEasyProvider,
    "dynu": DynuProvider,
    "gehirn": GehirnProvider,
    "google": GoogleProvider,
    "infomaniak": InfomaniakProvider,
    "ionos": IonosProvider,
    "linode": LinodeProvider,
    "luadns": LuaDnsProvider,
    "njalla": NjallaProvider,
    "nsone": NSOneProvider,
    "ovh": OvhProvider,
    "rfc2136": Rfc2136Provider,
    "route53": Route53Provider,
    "sakuracloud": SakuraCloudProvider,
    "scaleway": ScalewayProvider,
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


def extract_provider(service: str, authenticator: str = "", db=None) -> Optional[Provider]:
    credential_key = f"{service}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" if IS_MULTISITE else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
    credential_items = {}

    # First, try to get credentials from environment variables
    for env_key, env_value in environ.items():
        if not env_value or not env_key.startswith(credential_key):
            continue

        if " " not in env_value:
            credential_items["json_data"] = env_value
            continue

        key, value = env_value.split(" ", 1)
        credential_items[key.lower()] = value.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()

    # If no credentials found in environment, try database configuration
    if not credential_items and db:
        try:
            # Get database configuration for this service
            db_config = db.get_config(service=service if IS_MULTISITE else None)
            
            if IS_MULTISITE:
                # For multisite, check service-specific credential
                db_credential_value = db_config.get(f"{service}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", {}).get("value", "")
            else:
                # For single site, check global credential
                db_credential_value = db_config.get("LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", {}).get("value", "")
            
            if db_credential_value:
                LOGGER.debug(f"[Service: {service}] Found DNS credentials in database configuration")
                
                if " " not in db_credential_value:
                    credential_items["json_data"] = db_credential_value
                else:
                    key, value = db_credential_value.split(" ", 1)
                    credential_items[key.lower()] = value.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
            else:
                LOGGER.debug(f"[Service: {service}] No DNS credentials found in database for key: {credential_key}")
                
        except Exception as e:
            LOGGER.debug(f"[Service: {service}] Error accessing database configuration: {e}")
            LOGGER.debug(format_exc())

    # Handle JSON data
    if "json_data" in credential_items:
        value = credential_items.pop("json_data")
        if not credential_items and len(value) % 4 == 0 and match(r"^[A-Za-z0-9+/=]+$", value):
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
    if credential_items:
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

    # Log credential items for debugging (excluding sensitive values)
    LOGGER.debug(f"[Service: {service}] Processing credential items for authenticator '{authenticator}': {list(credential_items.keys())}")

    try:
        provider = PROVIDERS[authenticator](**credential_items)
        LOGGER.debug(f"[Service: {service}] Successfully validated credentials for DNS provider '{authenticator}'")
        return provider
    except ValidationError as ve:
        LOGGER.debug(format_exc())
        LOGGER.error(f"[Service: {service}] Error while validating credentials for DNS provider '{authenticator}', skipping generation: {ve}")
        return None
    except Exception as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"[Service: {service}] Unexpected error while creating DNS provider '{authenticator}': {e}")
        return None


def build_service_config(service: str, db=None) -> Tuple[str, Dict[str, Union[str, bool, int, Dict[str, str]]]]:
    def env(key: str, default: Optional[str] = None) -> str:
        # First try environment variables
        if IS_MULTISITE:
            env_value = getenv(f"{service}_{key}", None)
        else:
            env_value = getenv(key, None)
        
        if env_value is not None:
            return env_value
        
        # If not found in environment, try database configuration
        if db:
            try:
                db_config = db.get_config(service=service if IS_MULTISITE else None)
                
                if IS_MULTISITE:
                    db_key = f"{service}_{key}"
                else:
                    db_key = key
                    
                db_value = db_config.get(db_key, {}).get("value", "")
                if db_value:
                    LOGGER.debug(f"[Service: {service}] Using database value for {db_key}")
                    return db_value
            except Exception as e:
                LOGGER.debug(f"[Service: {service}] Error accessing database for key {key}: {e}")
        
        return default or ""

    authenticator = env("LETS_ENCRYPT_DNS_PROVIDER", "").lower()
    server_names_val = env("SERVER_NAME", "www.example.com").strip()
    email_val = env("EMAIL_LETS_ENCRYPT", "") or f"contact@{service}"
    retries_val = env("LETS_ENCRYPT_RETRIES", "0")
    challenge_val = env("LETS_ENCRYPT_CHALLENGE", "http").lower()
    profile_val = env("LETS_ENCRYPT_PROFILE", "classic").lower()
    custom_profile = env("LETS_ENCRYPT_CUSTOM_PROFILE", "").lower()
    dns_propagation_val = env("LETS_ENCRYPT_DNS_PROPAGATION", DNS_PROPAGATION_DEFAULT).lower()
    wildcard = env("USE_LETS_ENCRYPT_WILDCARD", "no").lower() == "yes"
    activated = env("AUTO_LETS_ENCRYPT", "no").lower() == "yes" and env("LETS_ENCRYPT_PASSTHROUGH", "no").lower() == "no"

    # User-friendly checks
    if activated and not server_names_val:
        LOGGER.warning(f"[Service: {service}] SERVER_NAME is empty. Please set a valid server name, skipping generation.")
        activated = False

    if "@" not in email_val:
        if activated:
            LOGGER.warning(f"[Service: {service}] EMAIL_LETS_ENCRYPT is missing or invalid. Using default: 'contact@{service}'")
        email_val = f"contact@{service}"

    try:
        retries_int = int(retries_val)
        if retries_int < 0:
            if activated:
                LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_RETRIES is negative. Defaulting to 0.")
            retries_int = 0
    except Exception:
        if activated:
            LOGGER.warning(f"[Service: {service}] LETS_ENCRYPT_RETRIES is not a valid integer. Defaulting to 0.")
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
            provider = extract_provider(service, authenticator, db)
            if not provider:
                activated = False
    else:
        authenticator = "manual"
        if wildcard:
            LOGGER.debug(f"[Service: {service}] Wildcard domains are not supported for HTTP challenges, deactivating wildcard support.")
            wildcard = False

    server_names = server_names_val.split(" ")
    server_name = service
    if wildcard:
        server_names = extract_wildcards_from_domains(server_names)
        server_name = server_names[-1] if server_names else service

    return server_name, {
        "server_names": ",".join(server_names),
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


def extract_wildcards_from_domains(domains: List[str]) -> List[str]:
    wildcards = set()
    for domain in domains:
        parts = domain.split(".")
        if len(parts) > 2:
            base_domain = ".".join(parts[1:])
            wildcards.add(f"*.{base_domain}")
            wildcards.add(base_domain)
        else:
            wildcards.add(domain)

    return sorted(wildcards, key=lambda x: x[0] != "*")


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


def certbot_new(config: Dict[str, Union[str, bool, int, Dict[str, str]]], cmd_env: Dict[str, str] = None) -> int:
    # * Building the certbot command
    # Ensure all necessary directories exist
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
    Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
    
    command = [
        CERTBOT_BIN,
        "certonly",
        "-n",
        "-d",
        config["server_names"],
        "--preferred-profile",
        config["profile"],
        "--agree-tos",
        "--config-dir",
        DATA_PATH.as_posix(),
        "--work-dir",
        WORK_DIR,
        "--logs-dir",
        LOGS_DIR,
        "--email",
        config["email"],
        "--break-my-certs",
        "--expand",
    ]

    if LOG_LEVEL == "DEBUG":
        command.append("-v")

    if not cmd_env:
        cmd_env = {}

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
        
        # Ensure cache directory exists
        CACHE_PATH.mkdir(parents=True, exist_ok=True)
        
        if not credentials_path.is_file() or config["force_renew"]:
            cached, err = JOB.cache_file(credentials_file, credentials)
            if not cached:
                LOGGER.error(f"[Service: {service}] Failed to cache credentials file: {err}")
                return 2
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

    current_date = datetime.now()
    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=cmd_env)

    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 2)
            if rlist:
                for line in process.stderr:
                    LOGGER_CERTBOT.info(line.strip())
                    break

        if datetime.now() - current_date > timedelta(seconds=5):
            LOGGER.info(
                "⏳ Still generating certificate(s)" + (" (this may take a while depending on the provider)" if config["challenge"] == "dns" else "") + "..."
            )
            current_date = datetime.now()

    return process.returncode


try:
    # ? Load services configuration
    server_names = getenv("SERVER_NAME", "www.example.com").strip()

    if not server_names:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    # Initialize database for configuration retrieval
    db = None
    try:
        from Database import Database  # type: ignore
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
        LOGGER.debug("Database connection established for configuration retrieval")
    except Exception as e:
        LOGGER.debug(f"Could not establish database connection: {e}")
        LOGGER.debug("Will rely on environment variables only")

    services = {}
    for service in server_names.split(" "):
        if not service.strip():
            continue

        server_name, config = build_service_config(service, db)
        if config["wildcard"] and server_name in services:
            continue
        services[server_name] = config

    if not any(service["activated"] for service in services.values()):
        LOGGER.info("No services uses Let's Encrypt, skipping generation of new certificates...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__.replace("new", "renew"))

    # ? Fetch existing certificates
    cmd_env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "RELOAD_MIN_TIMEOUT": getenv("RELOAD_MIN_TIMEOUT", "5"),
        "DISABLE_CONFIGURATION_TESTING": getenv("DISABLE_CONFIGURATION_TESTING", "no").lower(),
    }
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

            service = certificate_lines[0].split(" ")[0].strip()
            match_domains = search(r"Domains:\s+(.+)$", certificate_block, MULTILINE)
            domains = match_domains.group(1).strip().replace(" ", ",") if match_domains else ""

            existing_certificates[service] = {"active": False, "server_names": domains}

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

            if check_psl_blacklist(config["server_names"].split(","), psl_rules, server_name):
                config["activated"] = False
                continue

        if set(config["server_names"].split(",")) != set(existing_cert["server_names"].split(",")):
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

        if config["challenge"] == "dns" and config.get("provider") and bytes_hash(config["provider"].get_formatted_credentials(), algorithm="sha256") != existing_cert["credentials_hash"]:
            LOGGER.warning(f"[Service: {server_name}] DNS credentials have changed, forcing renewal.")
            config["force_renew"] = True

    # ? generate new certificates and renew existing ones if needed
    for service, config in services.items():
        if existing_certificates.get(service, {}).get("active") and not config["force_renew"]:
            LOGGER.info(f"Certificate(s) for {service} already exist, skipping generation.")
            config["exists"] = True
            continue
        elif not config["activated"]:
            continue

        LOGGER.info(
            f"Asking{' wildcard' if config['wildcard'] else ''} certificates for domain(s) : {config['server_names']} (email = {config['email']}){' using staging' if config['staging'] else ''} with {config['challenge']} challenge, using {config['profile']!r} profile..."
        )
        LOGGER.debug(f"Service configuration: {config}")

        for attempts in range(1, config["retries"] + 2):
            if attempts > 1:
                LOGGER.warning(f"Certificate generation failed, retrying... (attempt {attempts}/{config['retries'] + 1})")
                # Wait before retrying (exponential backoff: 30s, 60s, 120s...)
                wait_time = min(30 * (2 ** (attempts - 2)), 300)  # Cap at 5 minutes
                LOGGER.info(f"Waiting {wait_time} seconds before retry...")
                sleep(wait_time)

            ret = certbot_new(config, cmd_env.copy())

            if ret == 0:
                LOGGER.info(f"Certificate(s) for {service} generated successfully.")
                config["exists"] = True
                status = 1 if status == 0 else status
                break

            attempts += 1

        if not config["exists"]:
            status = 2
            LOGGER.error(f"Failed to generate certificate(s) for {service} after {config['retries'] + 1} attempts.")

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
