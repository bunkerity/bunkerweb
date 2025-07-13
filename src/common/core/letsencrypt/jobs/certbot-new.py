#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from base64 import b64decode
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta
from json import dumps, loads
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, match, search
from select import select
from subprocess import DEVNULL, PIPE, STDOUT, Popen, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from typing import Dict, Literal, Type, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from pydantic import ValidationError
from requests import get

from letsencrypt import (
    CloudflareProvider,
    DesecProvider,
    DigitalOceanProvider,
    DnsimpleProvider,
    DnsMadeEasyProvider,
    GehirnProvider,
    GoogleProvider,
    InfomaniakProvider,
    IonosProvider,
    LinodeProvider,
    LuaDnsProvider,
    NjallaProvider,
    NSOneProvider,
    OvhProvider,
    Rfc2136Provider,
    Route53Provider,
    SakuraCloudProvider,
    ScalewayProvider,
    WildcardGenerator,
)

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from bw_logger import setup_logger

# Initialize bw_logger module for Let's Encrypt certificate generation
logger = setup_logger(
    title="letsencrypt-certbot-new",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-certbot-new")

# Certificate generation binary and paths configuration
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

# Additional logger for certbot subprocess output
logger_certbot = setup_logger(
    title="letsencrypt-certbot-new-subprocess",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

status = 0

# Directory paths for Let's Encrypt operations
PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

# Public Suffix List configuration for domain validation
PSL_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
PSL_STATIC_FILE = "public_suffix_list.dat"

# Load and cache the Public Suffix List for domain validation.
# Downloads fresh copy if cache is older than 1 day, falls back to local file.
def load_public_suffix_list(job):
    logger.debug("Loading Public Suffix List for domain validation")
    
    job_cache = job.get_cache(PSL_STATIC_FILE, with_info=True, with_data=True)
    logger.debug(f"PSL cache check - exists: {isinstance(job_cache, dict)}")
    
    if (
        isinstance(job_cache, dict)
        and job_cache.get("last_update")
        and job_cache["last_update"] < (datetime.now().astimezone() - timedelta(days=1)).timestamp()
    ):
        logger.debug("Using cached PSL data (less than 1 day old)")
        return job_cache["data"].decode("utf-8").splitlines()

    try:
        logger.debug(f"Downloading fresh PSL from {PSL_URL}")
        resp = get(PSL_URL, timeout=5)
        resp.raise_for_status()
        content = resp.text
        logger.debug(f"PSL downloaded successfully, {len(content)} chars")
        
        cached, err = JOB.cache_file(PSL_STATIC_FILE, content.encode("utf-8"))
        if not cached:
            logger.error(f"Error while saving public suffix list to cache : {err}")
        else:
            logger.debug("PSL cached successfully")
        return content.splitlines()
    except BaseException as e:
        logger.exception("Error while downloading public suffix list")
        logger.error(f"PSL download error details: {e}")
        
        if PSL_STATIC_FILE.exists():
            logger.debug("Falling back to local PSL file")
            with PSL_STATIC_FILE.open("r", encoding="utf-8") as f:
                return f.read().splitlines()
        logger.warning("No PSL data available (download failed and no local file)")
        return []

# Parse Public Suffix List into rules and exceptions for domain validation.
# Separates normal rules from exception rules (prefixed with !).
def parse_psl(psl_lines):
    logger.debug(f"Parsing PSL with {len(psl_lines)} lines")
    
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
    
    logger.debug(f"PSL parsed - rules: {len(rules)}, exceptions: {len(exceptions)}")
    return {"rules": rules, "exceptions": exceptions}

# Check if domain is forbidden by Public Suffix List rules.
# Returns True if domain should be blocked from certificate generation.
def is_domain_blacklisted(domain, psl):
    logger.debug(f"Checking PSL blacklist status for domain: {domain}")
    
    # Returns True if the domain is forbidden by PSL rules
    domain = domain.lower().strip(".")
    labels = domain.split(".")
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        # Allow if candidate is an exception
        if candidate in psl["exceptions"]:
            logger.debug(f"Domain {domain} allowed by PSL exception: {candidate}")
            return False
        # Block if candidate matches a PSL rule
        if candidate in psl["rules"]:
            if i == 0:
                logger.debug(f"Domain {domain} blocked by PSL rule (exact match): {candidate}")
                return True  # Block exact match
            if i == 0 and domain.startswith("*."):
                logger.debug(f"Domain {domain} blocked by PSL rule (wildcard): {candidate}")
                return True  # Block wildcard for the rule itself
            if i == 0 or (i == 1 and labels[0] == "*"):
                logger.debug(f"Domain {domain} blocked by PSL rule (subdomain): {candidate}")
                return True  # Block *.domain.tld
            if len(labels[i:]) == len(labels):
                logger.debug(f"Domain {domain} blocked by PSL rule (domain.tld): {candidate}")
                return True  # Block domain.tld
            # Allow subdomains
        # Block if candidate matches a PSL wildcard rule
        if f"*.{candidate}" in psl["rules"]:
            if len(labels[i:]) == 2:
                logger.debug(f"Domain {domain} blocked by PSL wildcard rule: *.{candidate}")
                return True  # Block foo.bar and *.foo.bar
    
    logger.debug(f"Domain {domain} allowed by PSL check")
    return False

# Execute certbot with retry mechanism for certificate generation.
# Implements exponential backoff between retry attempts.
def certbot_new_with_retry(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: str = None,
    credentials_path: Union[str, Path] = None,
    propagation: str = "default",
    profile: str = "classic",
    staging: bool = False,
    force: bool = False,
    cmd_env: Dict[str, str] = None,
    max_retries: int = 0,
) -> int:
    logger.debug(f"Starting certbot with retry - max_retries: {max_retries}, domains: {domains}")
    
    attempt = 1
    while attempt <= max_retries + 1:  # +1 for the initial attempt
        if attempt > 1:
            logger.warning(f"Certificate generation failed, retrying... (attempt {attempt}/{max_retries + 1})")
            # Wait before retrying (exponential backoff: 30s, 60s, 120s...)
            wait_time = min(30 * (2 ** (attempt - 2)), 300)  # Cap at 5 minutes
            logger.info(f"Waiting {wait_time} seconds before retry...")
            sleep(wait_time)

        logger.debug(f"Executing certbot attempt {attempt}")
        result = certbot_new(
            challenge_type,
            domains,
            email,
            provider,
            credentials_path,
            propagation,
            profile,
            staging,
            force,
            cmd_env,
        )

        if result == 0:
            if attempt > 1:
                logger.info(f"Certificate generation succeeded on attempt {attempt}")
            logger.debug(f"Certbot completed successfully on attempt {attempt}")
            return result

        if attempt >= max_retries + 1:
            logger.error(f"Certificate generation failed after {max_retries + 1} attempts")
            return result

        attempt += 1

    return result

# Execute certbot command for certificate generation with specified parameters.
# Handles both DNS and HTTP challenges with provider-specific configuration.
def certbot_new(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: str = None,
    credentials_path: Union[str, Path] = None,
    propagation: str = "default",
    profile: str = "classic",
    staging: bool = False,
    force: bool = False,
    cmd_env: Dict[str, str] = None,
) -> int:
    logger.debug(f"Executing certbot_new - challenge: {challenge_type}, domains: {domains}, "
                f"provider: {provider}, staging: {staging}, force: {force}")
    
    if isinstance(credentials_path, str):
        credentials_path = Path(credentials_path)

    # * Building the certbot command
    command = [
        CERTBOT_BIN,
        "certonly",
        "--config-dir",
        DATA_PATH.as_posix(),
        "--work-dir",
        WORK_DIR,
        "--logs-dir",
        LOGS_DIR,
        "-n",
        "-d",
        domains,
        "--email",
        email,
        "--agree-tos",
        "--expand",
        f"--preferred-profile={profile}",
    ]
    logger.debug(f"Base certbot command built with {len(command)} arguments")

    if not cmd_env:
        cmd_env = {}

    if challenge_type == "dns":
        logger.debug(f"Configuring DNS challenge with provider: {provider}")
        # * Adding DNS challenge hooks
        command.append("--preferred-challenges=dns")

        # * Adding the propagation time to the command
        if propagation != "default":
            if not propagation.isdigit():
                logger.warning(f"Invalid propagation time : {propagation}, using provider's default...")
            else:
                logger.debug(f"Setting DNS propagation time: {propagation} seconds")
                command.extend([f"--dns-{provider}-propagation-seconds", propagation])

        # * Adding the credentials to the command
        if provider == "route53":
            logger.debug("Configuring Route53 credentials via environment variables")
            # ? Route53 credentials are different from the others, we need to add them to the environment
            with credentials_path.open("r") as file:
                for line in file:
                    key, value = line.strip().split("=", 1)
                    cmd_env[key] = value
                    logger.debug(f"Added Route53 credential: {key}")
        else:
            logger.debug(f"Setting credentials file path: {credentials_path}")
            command.extend([f"--dns-{provider}-credentials", credentials_path.as_posix()])

        # * Adding the RSA key size argument like in the infomaniak plugin documentation
        if provider in ("infomaniak", "ionos"):
            logger.debug(f"Setting RSA key size to 4096 for provider: {provider}")
            command.extend(["--rsa-key-size", "4096"])

        # * Adding plugin argument
        if provider in ("desec", "infomaniak", "ionos", "njalla", "scaleway"):
            logger.debug(f"Using authenticator format for provider: {provider}")
            # ? Desec, Infomaniak, IONOS, Njalla and Scaleway plugins use different arguments
            command.extend(["--authenticator", f"dns-{provider}"])
        else:
            logger.debug(f"Using standard DNS plugin format for provider: {provider}")
            command.append(f"--dns-{provider}")

    elif challenge_type == "http":
        logger.debug("Configuring HTTP challenge with manual hooks")
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

    if staging:
        logger.debug("Using staging environment")
        command.append("--staging")

    if force:
        logger.debug("Forcing certificate renewal")
        command.append("--force-renewal")

    if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG":
        logger.debug("Adding verbose output to certbot")
        command.append("-v")

    logger.debug(f"Final certbot command: {' '.join(command)}")
    current_date = datetime.now()
    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=cmd_env)
    logger.debug(f"Certbot process started with PID: {process.pid}")

    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 2)
            if rlist:
                for line in process.stderr:
                    logger_certbot.info(line.strip())
                    break

        if datetime.now() - current_date > timedelta(seconds=5):
            logger.info(
                "⏳ Still generating certificate(s)" + (" (this may take a while depending on the provider)" if challenge_type == "dns" else "") + "..."
            )
            current_date = datetime.now()

    logger.debug(f"Certbot process completed with return code: {process.returncode}")
    return process.returncode

# Check if running in multisite mode based on environment variable
IS_MULTISITE = getenv("MULTISITE", "no") == "yes"
logger.debug(f"Multisite mode: {IS_MULTISITE}")

try:
    # Get server names from environment configuration
    servers = getenv("SERVER_NAME", "www.example.com").lower() or []
    logger.debug(f"Raw SERVER_NAME value: {getenv('SERVER_NAME', 'www.example.com')}")

    if isinstance(servers, str):
        servers = servers.split(" ")

    logger.debug(f"Processed server list: {servers}")

    if not servers:
        logger.warning("There are no server names, skipping generation...")
        sys_exit(0)

    # Initialize Let's Encrypt usage flags
    use_letsencrypt = False
    use_letsencrypt_dns = False

    # Configure domains based on multisite mode
    if not IS_MULTISITE:
        logger.debug("Processing single-site configuration")
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        use_letsencrypt_dns = getenv("LETS_ENCRYPT_CHALLENGE", "http") == "dns"
        domains_server_names = {servers[0]: " ".join(servers).lower()}
        logger.debug(f"Single-site domains mapping: {domains_server_names}")
    else:
        logger.debug("Processing multi-site configuration")
        domains_server_names = {}

        for first_server in servers:
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True
                logger.debug(f"Let's Encrypt enabled for server: {first_server}")

            if first_server and getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http") == "dns":
                use_letsencrypt_dns = True
                logger.debug(f"DNS challenge enabled for server: {first_server}")

            domains_server_names[first_server] = getenv(f"{first_server}_SERVER_NAME", first_server).lower()

        logger.debug(f"Multi-site domains mapping: {domains_server_names}")

    if not use_letsencrypt:
        logger.info("Let's Encrypt is not activated, skipping generation...")
        sys_exit(0)

    # Initialize DNS provider classes if DNS challenge is used
    provider_classes = {}

    if use_letsencrypt_dns:
        logger.debug("Initializing DNS provider classes")
        provider_classes: Dict[
            str,
            Union[
                Type[CloudflareProvider],
                Type[DesecProvider],
                Type[DigitalOceanProvider],
                Type[DnsimpleProvider],
                Type[DnsMadeEasyProvider],
                Type[GehirnProvider],
                Type[GoogleProvider],
                Type[InfomaniakProvider],
                Type[IonosProvider],
                Type[LinodeProvider],
                Type[LuaDnsProvider],
                Type[NjallaProvider],
                Type[NSOneProvider],
                Type[OvhProvider],
                Type[Rfc2136Provider],
                Type[Route53Provider],
                Type[SakuraCloudProvider],
                Type[ScalewayProvider],
            ],
        ] = {
            "cloudflare": CloudflareProvider,
            "desec": DesecProvider,
            "digitalocean": DigitalOceanProvider,
            "dnsimple": DnsimpleProvider,
            "dnsmadeeasy": DnsMadeEasyProvider,
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
        logger.debug(f"Initialized {len(provider_classes)} DNS providers")

    # Initialize Job handler for cache management
    JOB = Job(logger, __file__)
    logger.debug("Job handler initialized")

    # ? Restore data from db cache of certbot-renew job
    logger.debug("Restoring cache from certbot-renew job")
    JOB.restore_cache(job_name="certbot-renew")

    # Setup environment variables for certbot execution
    env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "RELOAD_MIN_TIMEOUT": getenv("RELOAD_MIN_TIMEOUT", "5"),
        "DISABLE_CONFIGURATION_TESTING": getenv("DISABLE_CONFIGURATION_TESTING", "no").lower(),
    }
    env["PYTHONPATH"] = env["PYTHONPATH"] + (f":{DEPS_PATH}" if DEPS_PATH not in env["PYTHONPATH"] else "")
    if getenv("DATABASE_URI"):
        env["DATABASE_URI"] = getenv("DATABASE_URI")
    
    logger.debug(f"Environment configured - PYTHONPATH: {env['PYTHONPATH'][:100]}...")

    # Check existing certificates using certbot
    logger.debug("Checking existing certificates")
    proc = run(
        [
            CERTBOT_BIN,
            "certificates",
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
        env=env,
        check=False,
    )
    stdout = proc.stdout
    logger.debug(f"Certificate check completed with return code: {proc.returncode}")

    # Initialize certificate management objects
    WILDCARD_GENERATOR = WildcardGenerator()
    credential_paths = set()
    generated_domains = set()
    domains_to_ask = {}
    active_cert_names = set()  # Track ALL active certificate names, not just processed ones

    if proc.returncode != 0:
        logger.error(f"Error while checking certificates :\n{proc.stdout}")
    else:
        logger.debug("Processing existing certificate information")
        certificate_blocks = stdout.split("Certificate Name: ")[1:]
        logger.debug(f"Found {len(certificate_blocks)} existing certificate blocks")
        
        for first_server, domains in domains_server_names.items():
            if (getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") if IS_MULTISITE else getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
                continue

            logger.debug(f"Processing server: {first_server}")
            letsencrypt_challenge = getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http") if IS_MULTISITE else getenv("LETS_ENCRYPT_CHALLENGE", "http")
            original_first_server = deepcopy(first_server)

            # Handle wildcard domain processing
            if (
                letsencrypt_challenge == "dns"
                and (getenv(f"{original_first_server}_USE_LETS_ENCRYPT_WILDCARD", "no") if IS_MULTISITE else getenv("USE_LETS_ENCRYPT_WILDCARD", "no")) == "yes"
            ):
                logger.debug(f"Processing wildcard domains for {first_server}")
                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains((first_server,))
                first_server = wildcards[0].lstrip("*.")
                domains = set(wildcards)
                logger.debug(f"Wildcard processing result - base: {first_server}, domains: {domains}")
            else:
                domains = set(domains.split(" "))

            # Add the certificate name to our active set regardless if we're generating it or not
            active_cert_names.add(first_server)

            # Find matching certificate block
            certificate_block = None
            for block in certificate_blocks:
                if block.startswith(f"{first_server}\n"):
                    certificate_block = block
                    break

            if not certificate_block:
                domains_to_ask[first_server] = 1
                logger.warning(f"[{original_first_server}] Certificate block for {first_server} not found, asking new certificate...")
                continue

            try:
                cert_domains = search(r"Domains: (?P<domains>.*)\n\s*Expiry Date: (?P<expiry_date>.*)\n", certificate_block, MULTILINE)
            except BaseException as e:
                logger.exception(f"[{original_first_server}] Error while parsing certificate block")
                logger.error(f"[{original_first_server}] Parse error details: {e}")
                continue

            if not cert_domains:
                logger.error(f"[{original_first_server}] Failed to parse domains and expiry date from certificate block.")
                continue

            cert_domains_list = cert_domains.group("domains").strip().split()
            cert_domains_set = set(cert_domains_list)
            desired_domains_set = set(domains) if isinstance(domains, (list, set)) else set(domains.split())

            logger.debug(f"[{original_first_server}] Certificate domains: {cert_domains_set}")
            logger.debug(f"[{original_first_server}] Desired domains: {desired_domains_set}")

            if cert_domains_set != desired_domains_set:
                domains_to_ask[first_server] = 2
                logger.warning(
                    f"[{original_first_server}] Domains for {first_server} differ from desired set (existing: {sorted(cert_domains_set)}, desired: {sorted(desired_domains_set)}), asking new certificate..."
                )
                continue

            # Check staging environment consistency
            use_letsencrypt_staging = (
                getenv(f"{original_first_server}_USE_LETS_ENCRYPT_STAGING", "no") if IS_MULTISITE else getenv("USE_LETS_ENCRYPT_STAGING", "no")
            ) == "yes"
            is_test_cert = "TEST_CERT" in cert_domains.group("expiry_date")

            logger.debug(f"[{original_first_server}] Staging check - use_staging: {use_letsencrypt_staging}, is_test: {is_test_cert}")

            if (is_test_cert and not use_letsencrypt_staging) or (not is_test_cert and use_letsencrypt_staging):
                domains_to_ask[first_server] = 2
                logger.warning(f"[{original_first_server}] Certificate environment (staging/production) changed for {first_server}, asking new certificate...")
                continue

            # Get provider and profile information
            letsencrypt_provider = getenv(f"{original_first_server}_LETS_ENCRYPT_DNS_PROVIDER", "") if IS_MULTISITE else getenv("LETS_ENCRYPT_DNS_PROVIDER", "")
            letsencrypt_profile = (
                getenv(f"{original_first_server}_LETS_ENCRYPT_PROFILE", "classic") if IS_MULTISITE else getenv("LETS_ENCRYPT_PROFILE", "classic")
            )

            # Override profile if custom profile is set
            custom_profile = (
                getenv(f"{original_first_server}_LETS_ENCRYPT_CUSTOM_PROFILE", "") if IS_MULTISITE else getenv("LETS_ENCRYPT_CUSTOM_PROFILE", "")
            ).strip()
            if custom_profile:
                letsencrypt_profile = custom_profile
                logger.debug(f"[{original_first_server}] Using custom profile: {custom_profile}")

            # Check renewal file and validate provider/profile consistency
            renewal_file = DATA_PATH.joinpath("renewal", f"{first_server}.conf")
            if not renewal_file.is_file():
                logger.error(f"[{original_first_server}] Renewal file for {first_server} not found, asking new certificate...")
                domains_to_ask[first_server] = 1
                continue

            current_provider = None
            current_profile = "classic"
            logger.debug(f"[{original_first_server}] Reading renewal file: {renewal_file}")
            with renewal_file.open("r") as file:
                for line in file:
                    if line.startswith("authenticator"):
                        key, value = line.strip().split("=", 1)
                        current_provider = value.strip().replace("dns-", "")
                    elif line.startswith("preferred_profile"):
                        key, value = line.strip().split("=", 1)
                        current_profile = value.strip()

            logger.debug(f"[{original_first_server}] Renewal file analysis - provider: {current_provider}, profile: {current_profile}")

            # Check if profile has changed
            if current_profile != letsencrypt_profile:
                domains_to_ask[first_server] = 2
                logger.warning(
                    f"[{original_first_server}] Profile for {first_server} changed from {current_profile} to {letsencrypt_profile}, asking new certificate..."
                )
                continue

            # Validate DNS provider consistency
            if letsencrypt_challenge == "dns":
                if letsencrypt_provider and current_provider != letsencrypt_provider:
                    domains_to_ask[first_server] = 2
                    logger.warning(f"[{original_first_server}] Provider for {first_server} is not the same as in the certificate, asking new certificate...")
                    continue

                # Check if DNS credentials have changed
                if letsencrypt_provider and current_provider == letsencrypt_provider:
                    logger.debug(f"[{original_first_server}] Checking credential consistency for provider: {letsencrypt_provider}")
                    credential_key = f"{original_first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" if IS_MULTISITE else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
                    current_credential_items = {}

                    # Collect current credential items
                    for env_key, env_value in environ.items():
                        if env_value and env_key.startswith(credential_key):
                            if " " not in env_value:
                                current_credential_items["json_data"] = env_value
                                continue
                            key, value = env_value.split(" ", 1)
                            current_credential_items[key.lower()] = (
                                value.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                            )

                    if "json_data" in current_credential_items:
                        value = current_credential_items.pop("json_data")
                        if not current_credential_items and len(value) % 4 == 0 and match(r"^[A-Za-z0-9+/=]+$", value):
                            with suppress(BaseException):
                                decoded = b64decode(value).decode("utf-8")
                                json_data = loads(decoded)
                                if isinstance(json_data, dict):
                                    current_credential_items = {
                                        k.lower(): str(v).removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                                        for k, v in json_data.items()
                                    }

                    if current_credential_items:
                        logger.debug(f"[{original_first_server}] Found {len(current_credential_items)} credential items")
                        # Process regular credentials for base64 decoding
                        for key, value in current_credential_items.items():
                            if letsencrypt_provider != "rfc2136" and len(value) % 4 == 0 and match(r"^[A-Za-z0-9+/=]+$", value):
                                with suppress(BaseException):
                                    decoded = b64decode(value).decode("utf-8")
                                    if decoded != value:
                                        current_credential_items[key] = (
                                            decoded.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                                        )

                        # Generate current credentials content
                        if letsencrypt_provider in provider_classes:
                            with suppress(ValidationError, KeyError):
                                current_provider_instance = provider_classes[letsencrypt_provider](**current_credential_items)
                                current_credentials_content = current_provider_instance.get_formatted_credentials()

                                # Check if stored credentials file exists and compare
                                file_type = current_provider_instance.get_file_type()
                                stored_credentials_path = CACHE_PATH.joinpath(first_server, f"credentials.{file_type}")

                                if stored_credentials_path.is_file():
                                    stored_credentials_content = stored_credentials_path.read_bytes()
                                    if stored_credentials_content != current_credentials_content:
                                        domains_to_ask[first_server] = 2
                                        logger.warning(f"[{original_first_server}] DNS credentials for {first_server} have changed, asking new certificate...")
                                        continue
            elif current_provider != "manual" and letsencrypt_challenge == "http":
                domains_to_ask[first_server] = 2
                logger.warning(f"[{original_first_server}] {first_server} is no longer using DNS challenge, asking new certificate...")
                continue

            domains_to_ask[first_server] = 0
            logger.info(f"[{original_first_server}] Certificates already exist for domain(s) {domains}, expiry date: {cert_domains.group('expiry_date')}")

    # Initialize PSL data for domain validation
    psl_lines = None
    psl_rules = None

    # Process each server for certificate generation
    for first_server, domains in domains_server_names.items():
        if (getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") if IS_MULTISITE else getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
            logger.info(f"Let's Encrypt is not activated for {first_server}, skipping...")
            continue

        logger.debug(f"Processing certificate generation for server: {first_server}")

        # * Getting all the necessary data
        data = {
            "email": (getenv(f"{first_server}_EMAIL_LETS_ENCRYPT", "") if IS_MULTISITE else getenv("EMAIL_LETS_ENCRYPT", "")) or f"contact@{first_server}",
            "challenge": getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http") if IS_MULTISITE else getenv("LETS_ENCRYPT_CHALLENGE", "http"),
            "staging": (getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", "no") if IS_MULTISITE else getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes",
            "use_wildcard": (getenv(f"{first_server}_USE_LETS_ENCRYPT_WILDCARD", "no") if IS_MULTISITE else getenv("USE_LETS_ENCRYPT_WILDCARD", "no")) == "yes",
            "provider": getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER", "") if IS_MULTISITE else getenv("LETS_ENCRYPT_DNS_PROVIDER", ""),
            "propagation": (
                getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROPAGATION", "default") if IS_MULTISITE else getenv("LETS_ENCRYPT_DNS_PROPAGATION", "default")
            ),
            "profile": getenv(f"{first_server}_LETS_ENCRYPT_PROFILE", "classic") if IS_MULTISITE else getenv("LETS_ENCRYPT_PROFILE", "classic"),
            "check_psl": (
                getenv(f"{first_server}_LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", "yes") if IS_MULTISITE else getenv("LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", "yes")
            )
            == "no",
            "max_retries": getenv(f"{first_server}_LETS_ENCRYPT_MAX_RETRIES", "0") if IS_MULTISITE else getenv("LETS_ENCRYPT_MAX_RETRIES", "0"),
            "credential_items": {},
        }

        # Override profile if custom profile is set
        custom_profile = (getenv(f"{first_server}_LETS_ENCRYPT_CUSTOM_PROFILE", "") if IS_MULTISITE else getenv("LETS_ENCRYPT_CUSTOM_PROFILE", "")).strip()
        if custom_profile:
            data["profile"] = custom_profile

        logger.debug(f"Server {first_server} configuration - challenge: {data['challenge']}, "
                    f"wildcard: {data['use_wildcard']}, staging: {data['staging']}")

        if data["challenge"] == "http" and data["use_wildcard"]:
            logger.warning(f"Wildcard is not supported with HTTP challenge, disabling wildcard for service {first_server}...")
            data["use_wildcard"] = False

        if (not data["use_wildcard"] and not domains_to_ask.get(first_server)) or (
            data["use_wildcard"] and not domains_to_ask.get(WILDCARD_GENERATOR.extract_wildcards_from_domains((first_server,))[0].lstrip("*."))
        ):
            continue

        if not data["max_retries"].isdigit():
            logger.warning(f"Invalid max retries value for service {first_server} : {data['max_retries']}, using default value of 0...")
            data["max_retries"] = 0
        else:
            data["max_retries"] = int(data["max_retries"])

        # * Getting the DNS provider data if necessary
        if data["challenge"] == "dns":
            logger.debug(f"Processing DNS credentials for {first_server} with provider {data['provider']}")
            credential_key = f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" if IS_MULTISITE else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
            credential_items = {}

            # Collect all credential items
            for env_key, env_value in environ.items():
                if env_value and env_key.startswith(credential_key):
                    if " " not in env_value:
                        credential_items["json_data"] = env_value
                        continue
                    key, value = env_value.split(" ", 1)
                    credential_items[key.lower()] = value.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()

            logger.debug(f"Found {len(credential_items)} raw credential items for {first_server}")

            if "json_data" in credential_items:
                value = credential_items.pop("json_data")
                # Handle the case of a single credential that might be base64-encoded JSON
                if not credential_items and len(value) % 4 == 0 and match(r"^[A-Za-z0-9+/=]+$", value):
                    try:
                        decoded = b64decode(value).decode("utf-8")
                        json_data = loads(decoded)
                        if isinstance(json_data, dict):
                            data["credential_items"] = {
                                k.lower(): str(v).removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                                for k, v in json_data.items()
                            }
                            logger.debug(f"Decoded JSON credentials for {first_server}")
                    except BaseException as e:
                        logger.exception(f"Error while decoding JSON data for service {first_server}")
                        logger.error(f"JSON decode error details: {value} : {e}")

            if not data["credential_items"]:
                # Process regular credentials
                data["credential_items"] = {}
                for key, value in credential_items.items():
                    # Check for base64 encoding
                    if data["provider"] != "rfc2136" and len(value) % 4 == 0 and match(r"^[A-Za-z0-9+/=]+$", value):
                        try:
                            decoded = b64decode(value).decode("utf-8")
                            if decoded != value:
                                value = decoded.removeprefix("= ").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").strip()
                                logger.debug(f"Decoded base64 credential item {key} for {first_server}")
                        except BaseException as e:
                            logger.exception(f"Error while decoding credential item {key} for service {first_server}")
                            logger.debug(f"Credential decode error details: {value} : {e}")
                    data["credential_items"][key] = value

        logger.debug(f"Data for service {first_server} : {dumps(data)}")

        # * Checking if the DNS data is valid
        if data["challenge"] == "dns":
            if not data["provider"]:
                logger.warning(
                    f"No provider found for service {first_server} (available providers : {', '.join(provider_classes.keys())}), skipping certificate(s) generation..."  # noqa: E501
                )
                continue
            elif data["provider"] not in provider_classes:
                logger.warning(
                    f"Provider {data['provider']} not found for service {first_server} (available providers : {', '.join(provider_classes.keys())}), skipping certificate(s) generation..."  # noqa: E501
                )
                continue
            elif not data["credential_items"]:
                logger.warning(
                    f"No valid credentials items found for service {first_server} (you should have at least one), skipping certificate(s) generation..."
                )
                continue

            # * Validating the credentials
            try:
                provider = provider_classes[data["provider"]](**data["credential_items"])
                logger.debug(f"DNS provider {data['provider']} validated successfully for {first_server}")
            except ValidationError as ve:
                logger.exception(f"Error while validating credentials for service {first_server}")
                logger.error(f"Credential validation error details: {ve}")
                continue

            content = provider.get_formatted_credentials()
        else:
            content = b"http_challenge"

        is_blacklisted = False

        # * Adding the domains to Wildcard Generator if necessary
        file_type = provider.get_file_type() if data["challenge"] == "dns" else "txt"
        file_path = (first_server, f"credentials.{file_type}")
        if data["use_wildcard"]:
            logger.debug(f"Processing wildcard configuration for {first_server}")
            # Use the improved method for generating consistent group names
            group = WILDCARD_GENERATOR.create_group_name(
                domain=first_server,
                provider=data["provider"] if data["challenge"] == "dns" else "http",
                challenge_type=data["challenge"],
                staging=data["staging"],
                content_hash=bytes_hash(content, algorithm="sha1"),
                profile=data["profile"],
            )

            logger.info(
                f"Service {first_server} is using wildcard, "
                + ("the propagation time will be the provider's default and " if data["challenge"] == "dns" else "")
                + "the email will be the same as the first domain that created the group..."
            )

            if data["check_psl"]:
                logger.debug(f"Checking PSL for wildcard domains for {first_server}")
                if psl_lines is None:
                    psl_lines = load_public_suffix_list(JOB)
                if psl_rules is None:
                    psl_rules = parse_psl(psl_lines)

                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains(domains.split(" "))

                logger.debug(f"Wildcard domains for {first_server} : {wildcards}")

                for d in wildcards:
                    if is_domain_blacklisted(d, psl_rules):
                        logger.error(f"Wildcard domain {d} is blacklisted by Public Suffix List, refusing certificate request for {first_server}.")
                        is_blacklisted = True
                        break

            if not is_blacklisted:
                WILDCARD_GENERATOR.extend(group, domains.split(" "), data["email"], data["staging"])
                file_path = (f"{group}.{file_type}",)
                logger.debug(f"[{first_server}] Wildcard group {group}")
        elif data["check_psl"]:
            logger.debug(f"Checking PSL for individual domains for {first_server}")
            if psl_lines is None:
                psl_lines = load_public_suffix_list(JOB)
            if psl_rules is None:
                psl_rules = parse_psl(psl_lines)

            for d in domains.split():
                if is_domain_blacklisted(d, psl_rules):
                    logger.error(f"Domain {d} is blacklisted by Public Suffix List, refusing certificate request for {first_server}.")
                    is_blacklisted = True
                    break

        if is_blacklisted:
            continue

        # * Generating the credentials file
        credentials_path = CACHE_PATH.joinpath(*file_path)
        logger.debug(f"Credentials path for {first_server}: {credentials_path}")

        if data["challenge"] == "dns":
            if not credentials_path.is_file():
                logger.debug(f"Creating new credentials file for {first_server}")
                cached, err = JOB.cache_file(
                    credentials_path.name, content, job_name="certbot-renew", service_id=first_server if not data["use_wildcard"] else ""
                )
                if not cached:
                    logger.error(f"Error while saving service {first_server}'s credentials file in cache : {err}")
                    continue
                logger.info(f"Successfully saved service {first_server}'s credentials file in cache")
            elif data["use_wildcard"]:
                logger.info(f"Service {first_server}'s wildcard credentials file has already been generated")
            else:
                logger.debug(f"Checking credentials file update for {first_server}")
                old_content = credentials_path.read_bytes()
                if old_content != content:
                    logger.warning(f"Service {first_server}'s credentials file is outdated, updating it...")
                    cached, err = JOB.cache_file(credentials_path.name, content, job_name="certbot-renew", service_id=first_server)
                    if not cached:
                        logger.error(f"Error while updating service {first_server}'s credentials file in cache : {err}")
                        continue
                    logger.info(f"Successfully updated service {first_server}'s credentials file in cache")
                else:
                    logger.info(f"Service {first_server}'s credentials file is up to date")

            credential_paths.add(credentials_path)
            credentials_path.chmod(0o600)  # ? Setting the permissions to 600 (this is important to avoid warnings from certbot)
            logger.debug(f"Set credentials file permissions to 600 for {first_server}")

        if data["use_wildcard"]:
            continue

        domains = domains.replace(" ", ",")
        logger.info(
            f"Asking certificates for domain(s) : {domains} (email = {data['email']}){' using staging' if data['staging'] else ''} with {data['challenge']} challenge, using {data['profile']!r} profile..."
        )

        if (
            certbot_new_with_retry(
                data["challenge"],
                domains,
                data["email"],
                data["provider"],
                credentials_path,
                data["propagation"],
                data["profile"],
                data["staging"],
                domains_to_ask[first_server] == 2,
                cmd_env=env,
                max_retries=data["max_retries"],
            )
            != 0
        ):
            status = 2
            logger.error(f"Certificate generation failed for domain(s) {domains} ...")
        else:
            status = 1 if status == 0 else status
            logger.info(f"Certificate generation succeeded for domain(s) : {domains}")

        generated_domains.update(domains.split(","))

    # * Generating the wildcards if necessary
    logger.debug("Processing wildcard certificate generation")
    wildcards = WILDCARD_GENERATOR.get_wildcards()
    if wildcards:
        logger.debug(f"Found {len(wildcards)} wildcard groups to process")
        for group, data in wildcards.items():
            if not data:
                continue
            # * Generating the certificate from the generated credentials
            group_parts = group.split("_")
            provider = group_parts[0]
            profile = group_parts[2]
            base_domain = group_parts[3]

            email = data.pop("email")
            credentials_file = CACHE_PATH.joinpath(f"{group}.{provider_classes[provider].get_file_type() if provider in provider_classes else 'txt'}")

            logger.debug(f"Processing wildcard group {group} with provider {provider}")

            # Process different environment types (staging/prod)
            for key, domains in data.items():
                if not domains:
                    continue

                staging = key == "staging"
                logger.info(
                    f"Asking wildcard certificates for domain(s): {domains} (email = {email})"
                    f"{' using staging ' if staging else ''} with {'dns' if provider in provider_classes else 'http'} challenge, "
                    f"using {profile!r} profile..."
                )

                domains_split = domains.split(",")

                # Add wildcard certificate names to active set
                for domain in domains_split:
                    # Extract the base domain from the wildcard domain
                    base_domain = WILDCARD_GENERATOR.get_base_domain(domain)
                    active_cert_names.add(base_domain)

                if (
                    certbot_new_with_retry(
                        "dns",
                        domains,
                        email,
                        provider,
                        credentials_file,
                        "default",
                        profile,
                        staging,
                        domains_to_ask.get(base_domain, 0) == 2,
                        cmd_env=env,
                    )
                    != 0
                ):
                    status = 2
                    logger.error(f"Certificate generation failed for domain(s) {domains} ...")
                else:
                    status = 1 if status == 0 else status
                    logger.info(f"Certificate generation succeeded for domain(s): {domains}")

                generated_domains.update(domains_split)
    else:
        logger.info("No wildcard domains found, skipping wildcard certificate(s) generation...")

    # Clean up old credential files
    if CACHE_PATH.is_dir():
        logger.debug("Cleaning up old credentials files")
        # * Clearing all missing credentials files
        for ext in ("*.ini", "*.env", "*.json"):
            for file in list(CACHE_PATH.rglob(ext)):
                if "etc" in file.parts or not file.is_file():
                    continue
                # ? If the file is not in the wildcard groups, remove it
                if file not in credential_paths:
                    logger.debug(f"Removing old credentials file {file}")
                    JOB.del_cache(file.name, job_name="certbot-renew", service_id=file.parent.name if file.parent.name != "letsencrypt" else "")

    # * Clearing all no longer needed certificates
    if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
        logger.info("Clear old certificates is activated, removing old / no longer used certificates...")

        # Get list of all certificates
        proc = run(
            [
                CERTBOT_BIN,
                "certificates",
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
            env=env,
            check=False,
        )

        if proc.returncode == 0:
            certificate_blocks = proc.stdout.split("Certificate Name: ")[1:]
            logger.debug(f"Found {len(certificate_blocks)} certificates for cleanup evaluation")
            for block in certificate_blocks:
                cert_name = block.split("\n", 1)[0].strip()

                # Skip certificates that are in our active list
                if cert_name in active_cert_names:
                    logger.debug(f"Keeping active certificate: {cert_name}")
                    continue

                logger.warning(f"Removing old certificate {cert_name} (not in active certificates list)")

                # Use certbot's delete command
                delete_proc = run(
                    [
                        CERTBOT_BIN,
                        "delete",
                        "--config-dir",
                        DATA_PATH.as_posix(),
                        "--work-dir",
                        WORK_DIR,
                        "--logs-dir",
                        LOGS_DIR,
                        "--cert-name",
                        cert_name,
                        "-n",  # non-interactive
                    ],
                    stdin=DEVNULL,
                    stdout=PIPE,
                    stderr=STDOUT,
                    text=True,
                    env=env,
                    check=False,
                )

                if delete_proc.returncode == 0:
                    logger.info(f"Successfully deleted certificate {cert_name}")
                    # Remove any remaining files for this certificate
                    cert_dir = DATA_PATH.joinpath("live", cert_name)
                    archive_dir = DATA_PATH.joinpath("archive", cert_name)
                    renewal_file = DATA_PATH.joinpath("renewal", f"{cert_name}.conf")
                    for path in (cert_dir, archive_dir):
                        if path.exists():
                            try:
                                for file in path.glob("*"):
                                    try:
                                        file.unlink()
                                    except Exception as e:
                                        logger.error(f"Failed to remove file {file}: {e}")
                                path.rmdir()
                                logger.info(f"Removed directory {path}")
                            except Exception as e:
                                logger.error(f"Failed to remove directory {path}: {e}")
                        if renewal_file.exists():
                            try:
                                renewal_file.unlink()
                                logger.info(f"Removed renewal file {renewal_file}")
                            except Exception as e:
                                logger.error(f"Failed to remove renewal file {renewal_file}: {e}")
                else:
                    logger.error(f"Failed to delete certificate {cert_name}: {delete_proc.stdout}")
        else:
            logger.error(f"Error listing certificates: {proc.stdout}")

    # * Save data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        logger.debug("Saving certificate data to database cache")
        cached, err = JOB.cache_dir(DATA_PATH, job_name="certbot-renew")
        if not cached:
            logger.error(f"Error while saving data to db cache : {err}")
        else:
            logger.info("Successfully saved data to db cache")
except SystemExit as e:
    status = e.code
    logger.debug(f"Script exiting with SystemExit code: {e.code}")
except BaseException as e:
    status = 1
    logger.exception("Exception occurred while running certbot-new.py")
    logger.error(f"Exception details: {type(e).__name__}: {e}")

logger.debug(f"Certificate generation script completed with final status: {status}")
sys_exit(status)
