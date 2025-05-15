#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from base64 import b64decode
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
from traceback import format_exc
from typing import Dict, Literal, Type, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
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
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("LETS-ENCRYPT.new")
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT.new.certbot")
status = 0

PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

PSL_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
PSL_STATIC_FILE = "public_suffix_list.dat"


def load_public_suffix_list(job):
    job_cache = job.get_cache(PSL_STATIC_FILE, with_info=True, with_data=True)
    if isinstance(job_cache, dict) and job_cache["last_update"] < (datetime.now().astimezone() - timedelta(days=1)).timestamp():
        return job_cache["data"].decode("utf-8").splitlines()

    try:
        resp = get(PSL_URL, timeout=5)
        resp.raise_for_status()
        content = resp.text
        cached, err = JOB.cache_file(PSL_STATIC_FILE, content.encode("utf-8"))
        if not cached:
            LOGGER.error(f"Error while saving public suffix list to cache : {err}")
        return content.splitlines()
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while downloading public suffix list : {e}")
        if PSL_STATIC_FILE.exists():
            with PSL_STATIC_FILE.open("r", encoding="utf-8") as f:
                return f.read().splitlines()
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

    if not cmd_env:
        cmd_env = {}

    if challenge_type == "dns":
        # * Adding DNS challenge hooks
        command.append("--preferred-challenges=dns")

        # * Adding the propagation time to the command
        if propagation != "default":
            if not propagation.isdigit():
                LOGGER.warning(f"Invalid propagation time : {propagation}, using provider's default...")
            else:
                command.extend([f"--dns-{provider}-propagation-seconds", propagation])

        # * Adding the credentials to the command
        if provider == "route53":
            # ? Route53 credentials are different from the others, we need to add them to the environment
            with credentials_path.open("r") as file:
                for line in file:
                    key, value = line.strip().split("=", 1)
                    cmd_env[key] = value
        else:
            command.extend([f"--dns-{provider}-credentials", credentials_path.as_posix()])

        # * Adding the RSA key size argument like in the infomaniak plugin documentation
        if provider in ("infomaniak", "ionos"):
            command.extend(["--rsa-key-size", "4096"])

        # * Adding plugin argument
        if provider in ("desec", "infomaniak", "ionos", "scaleway"):
            # ? Desec, Infomaniak, IONOS and Scaleway plugins use different arguments
            command.extend(["--authenticator", f"dns-{provider}"])
        else:
            command.append(f"--dns-{provider}")

    elif challenge_type == "http":
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
        command.append("--staging")

    if force:
        command.append("--force-renewal")

    if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG":
        command.append("-v")

    current_date = datetime.now()
    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=cmd_env)

    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 1)  # 1-second timeout
            if rlist:
                for line in process.stderr:
                    LOGGER_CERTBOT.info(line.strip())
                    break

        if datetime.now() - current_date > timedelta(seconds=5):
            LOGGER.info(
                "⏳ Still generating certificate(s)" + (" (this may take a while depending on the provider)" if challenge_type == "dns" else "") + "..."
            )
            current_date = datetime.now()

    return process.returncode


IS_MULTISITE = getenv("MULTISITE", "no") == "yes"

try:
    servers = getenv("SERVER_NAME", "").lower() or []

    if isinstance(servers, str):
        servers = servers.split(" ")

    if not servers:
        LOGGER.warning("There are no server names, skipping generation...")
        sys_exit(0)

    use_letsencrypt = False
    use_letsencrypt_dns = False

    if not IS_MULTISITE:
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        use_letsencrypt_dns = getenv("LETS_ENCRYPT_CHALLENGE", "http") == "dns"
        domains_server_names = {servers[0]: " ".join(servers).lower()}
    else:
        domains_server_names = {}

        for first_server in servers:
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True

            if first_server and getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http") == "dns":
                use_letsencrypt_dns = True

            domains_server_names[first_server] = getenv(f"{first_server}_SERVER_NAME", first_server).lower()

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping generation...")
        sys_exit(0)

    provider_classes = {}

    if use_letsencrypt_dns:
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
            "nsone": NSOneProvider,
            "ovh": OvhProvider,
            "rfc2136": Rfc2136Provider,
            "route53": Route53Provider,
            "sakuracloud": SakuraCloudProvider,
            "scaleway": ScalewayProvider,
        }

    JOB = Job(LOGGER, __file__)

    # ? Restore data from db cache of certbot-renew job
    JOB.restore_cache(job_name="certbot-renew")

    env = environ.copy()
    env["PYTHONPATH"] = env.get("PYTHONPATH", "") + (f":{DEPS_PATH}" if DEPS_PATH not in env.get("PYTHONPATH", "") else "")

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

    WILDCARD_GENERATOR = WildcardGenerator()
    credential_paths = set()
    generated_domains = set()
    domains_to_ask = {}
    active_cert_names = set()  # Track ALL active certificate names, not just processed ones

    if proc.returncode != 0:
        LOGGER.error(f"Error while checking certificates :\n{proc.stdout}")
    else:
        certificate_blocks = stdout.split("Certificate Name: ")[1:]
        for first_server, domains in domains_server_names.items():
            if getenv(f"{first_server}_AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
                continue

            letsencrypt_challenge = getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", getenv("LETS_ENCRYPT_CHALLENGE", "http"))
            original_first_server = deepcopy(first_server)

            if letsencrypt_challenge == "dns" and getenv(f"{first_server}_USE_LETS_ENCRYPT_WILDCARD", getenv("USE_LETS_ENCRYPT_WILDCARD", "no")) == "yes":
                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains((first_server,))
                first_server = wildcards[0].lstrip("*.")
                domains = set(wildcards)
            else:
                domains = set(domains.split(" "))

            # Add the certificate name to our active set regardless if we're generating it or not
            active_cert_names.add(first_server)

            certificate_block = None
            for block in certificate_blocks:
                if block.startswith(f"{first_server}\n"):
                    certificate_block = block
                    break

            if not certificate_block:
                domains_to_ask[first_server] = 1
                LOGGER.warning(f"[{original_first_server}] Certificate block for {first_server} not found, asking new certificate...")
                continue

            try:
                cert_domains = search(r"Domains: (?P<domains>.*)\n\s*Expiry Date: (?P<expiry_date>.*)\n", certificate_block, MULTILINE)
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"[{original_first_server}] Error while parsing certificate block: {e}")
                continue

            if not cert_domains:
                LOGGER.error(f"[{original_first_server}] Failed to parse domains and expiry date from certificate block.")
                continue

            cert_domains_list = cert_domains.group("domains").strip().split()
            cert_domains_set = set(cert_domains_list)
            desired_domains_set = set(domains) if isinstance(domains, (list, set)) else set(domains.split())

            if cert_domains_set != desired_domains_set:
                domains_to_ask[first_server] = 2
                LOGGER.warning(
                    f"[{original_first_server}] Domains for {first_server} differ from desired set (existing: {sorted(cert_domains_set)}, desired: {sorted(desired_domains_set)}), asking new certificate..."
                )
                continue

            use_letsencrypt_staging = getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes"
            is_test_cert = "TEST_CERT" in cert_domains.group("expiry_date")

            if (is_test_cert and not use_letsencrypt_staging) or (not is_test_cert and use_letsencrypt_staging):
                domains_to_ask[first_server] = 2
                LOGGER.warning(f"[{original_first_server}] Certificate environment (staging/production) changed for {first_server}, asking new certificate...")
                continue

            letsencrypt_provider = getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER", getenv("LETS_ENCRYPT_DNS_PROVIDER", ""))

            renewal_file = DATA_PATH.joinpath("renewal", f"{first_server}.conf")
            if not renewal_file.is_file():
                LOGGER.error(f"[{original_first_server}] Renewal file for {first_server} not found, asking new certificate...")
                domains_to_ask[first_server] = 1
                continue

            current_provider = None
            with renewal_file.open("r") as file:
                for line in file:
                    if line.startswith("authenticator"):
                        key, value = line.strip().split("=", 1)
                        current_provider = value.strip().replace("dns-", "")
                        break

            if letsencrypt_challenge == "dns":
                if letsencrypt_provider and current_provider != letsencrypt_provider:
                    domains_to_ask[first_server] = 2
                    LOGGER.warning(f"[{original_first_server}] Provider for {first_server} is not the same as in the certificate, asking new certificate...")
                    continue
            elif current_provider != "manual" and letsencrypt_challenge == "http":
                domains_to_ask[first_server] = 2
                LOGGER.warning(f"[{original_first_server}] {first_server} is no longer using DNS challenge, asking new certificate...")
                continue

            domains_to_ask[first_server] = 0
            LOGGER.info(f"[{original_first_server}] Certificates already exist for domain(s) {domains}, expiry date: {cert_domains.group('expiry_date')}")

    psl_lines = None
    psl_rules = None

    for first_server, domains in domains_server_names.items():
        if getenv(f"{first_server}_AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
            LOGGER.info(f"Let's Encrypt is not activated for {first_server}, skipping...")
            continue

        # * Getting all the necessary data
        data = {
            "email": getenv(f"{first_server}_EMAIL_LETS_ENCRYPT", getenv("EMAIL_LETS_ENCRYPT", "")) or f"contact@{first_server}",
            "challenge": getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", getenv("LETS_ENCRYPT_CHALLENGE", "http")),
            "staging": getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes",
            "use_wildcard": getenv(f"{first_server}_USE_LETS_ENCRYPT_WILDCARD", getenv("USE_LETS_ENCRYPT_WILDCARD", "no")) == "yes",
            "provider": getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER", getenv("LETS_ENCRYPT_DNS_PROVIDER", "")),
            "propagation": getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROPAGATION", getenv("LETS_ENCRYPT_DNS_PROPAGATION", "default")),
            "profile": getenv(f"{first_server}_LETS_ENCRYPT_PROFILE", getenv("LETS_ENCRYPT_PROFILE", "classic")),
            "check_psl": getenv(f"{first_server}_LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", getenv("LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", "yes")) == "yes",
            "credential_items": {},
        }

        # Override profile if custom profile is set
        custom_profile = getenv(f"{first_server}_LETS_ENCRYPT_CUSTOM_PROFILE", getenv("LETS_ENCRYPT_CUSTOM_PROFILE", "")).strip()
        if custom_profile:
            data["profile"] = custom_profile

        if data["challenge"] == "http" and data["use_wildcard"]:
            LOGGER.warning(f"Wildcard is not supported with HTTP challenge, disabling wildcard for service {first_server}...")
            data["use_wildcard"] = False

        if (not data["use_wildcard"] and not domains_to_ask.get(first_server)) or (
            data["use_wildcard"] and not domains_to_ask.get(WILDCARD_GENERATOR.extract_wildcards_from_domains((first_server,))[0].lstrip("*."))
        ):
            continue

        # * Getting the DNS provider data if necessary
        if data["challenge"] == "dns":
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
                    except BaseException as e:
                        LOGGER.debug(format_exc())
                        LOGGER.error(f"Error while decoding JSON data for service {first_server} : {value} : \n{e}")

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
                        except BaseException as e:
                            LOGGER.debug(format_exc())
                            LOGGER.debug(f"Error while decoding credential item {key} for service {first_server} : {value} : \n{e}")
                    data["credential_items"][key] = value

        LOGGER.debug(f"Data for service {first_server} : {dumps(data)}")

        # * Checking if the DNS data is valid
        if data["challenge"] == "dns":
            if not data["provider"]:
                LOGGER.warning(
                    f"No provider found for service {first_server} (available providers : {', '.join(provider_classes.keys())}), skipping certificate(s) generation..."  # noqa: E501
                )
                continue
            elif data["provider"] not in provider_classes:
                LOGGER.warning(
                    f"Provider {data['provider']} not found for service {first_server} (available providers : {', '.join(provider_classes.keys())}), skipping certificate(s) generation..."  # noqa: E501
                )
                continue
            elif not data["credential_items"]:
                LOGGER.warning(
                    f"No valid credentials items found for service {first_server} (you should have at least one), skipping certificate(s) generation..."
                )
                continue

            # * Validating the credentials
            try:
                provider = provider_classes[data["provider"]](**data["credential_items"])
            except ValidationError as ve:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Error while validating credentials for service {first_server} :\n{ve}")
                continue

            content = provider.get_formatted_credentials()
        else:
            content = b"http_challenge"

        is_blacklisted = False

        # * Adding the domains to Wildcard Generator if necessary
        file_type = provider.get_file_type() if data["challenge"] == "dns" else "txt"
        file_path = (first_server, f"credentials.{file_type}")
        if data["use_wildcard"]:
            # Use the improved method for generating consistent group names
            group = WILDCARD_GENERATOR.create_group_name(
                domain=first_server,
                provider=data["provider"] if data["challenge"] == "dns" else "http",
                challenge_type=data["challenge"],
                staging=data["staging"],
                content_hash=bytes_hash(content, algorithm="sha1"),
                profile=data["profile"],
            )

            LOGGER.info(
                f"Service {first_server} is using wildcard, "
                + ("the propagation time will be the provider's default and " if data["challenge"] == "dns" else "")
                + "the email will be the same as the first domain that created the group..."
            )

            if data["check_psl"]:
                if psl_lines is None:
                    psl_lines = load_public_suffix_list(JOB)
                if psl_rules is None:
                    psl_rules = parse_psl(psl_lines)

                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains(domains.split(" "))

                LOGGER.debug(f"Wildcard domains for {first_server} : {wildcards}")

                for d in wildcards:
                    if is_domain_blacklisted(d, psl_rules):
                        LOGGER.error(f"Wildcard domain {d} is blacklisted by Public Suffix List, refusing certificate request for {first_server}.")
                        is_blacklisted = True
                        break

            if not is_blacklisted:
                WILDCARD_GENERATOR.extend(group, domains.split(" "), data["email"], data["staging"])
                file_path = (f"{group}.{file_type}",)
                LOGGER.debug(f"[{first_server}] Wildcard group {group}")
        elif data["check_psl"]:
            if psl_lines is None:
                psl_lines = load_public_suffix_list(JOB)
            if psl_rules is None:
                psl_rules = parse_psl(psl_lines)

            for d in domains.split():
                if is_domain_blacklisted(d, psl_rules):
                    LOGGER.error(f"Domain {d} is blacklisted by Public Suffix List, refusing certificate request for {first_server}.")
                    is_blacklisted = True
                    break

        if is_blacklisted:
            continue

        # * Generating the credentials file
        credentials_path = CACHE_PATH.joinpath(*file_path)

        if data["challenge"] == "dns":
            if not credentials_path.is_file():
                cached, err = JOB.cache_file(
                    credentials_path.name, content, job_name="certbot-renew", service_id=first_server if not data["use_wildcard"] else ""
                )
                if not cached:
                    LOGGER.error(f"Error while saving service {first_server}'s credentials file in cache : {err}")
                    continue
                LOGGER.info(f"Successfully saved service {first_server}'s credentials file in cache")
            elif data["use_wildcard"]:
                LOGGER.info(f"Service {first_server}'s wildcard credentials file has already been generated")
            else:
                old_content = credentials_path.read_bytes()
                if old_content != content:
                    LOGGER.warning(f"Service {first_server}'s credentials file is outdated, updating it...")
                    cached, err = JOB.cache_file(credentials_path.name, content, job_name="certbot-renew", service_id=first_server)
                    if not cached:
                        LOGGER.error(f"Error while updating service {first_server}'s credentials file in cache : {err}")
                        continue
                    LOGGER.info(f"Successfully updated service {first_server}'s credentials file in cache")
                else:
                    LOGGER.info(f"Service {first_server}'s credentials file is up to date")

            credential_paths.add(credentials_path)
            credentials_path.chmod(0o600)  # ? Setting the permissions to 600 (this is important to avoid warnings from certbot)

        if data["use_wildcard"]:
            continue

        domains = domains.replace(" ", ",")
        LOGGER.info(
            f"Asking certificates for domain(s) : {domains} (email = {data['email']}){' using staging' if data['staging'] else ''} with {data['challenge']} challenge, using {data['profile']!r} profile..."
        )

        if (
            certbot_new(
                data["challenge"],
                domains,
                data["email"],
                data["provider"],
                credentials_path,
                data["propagation"],
                data["profile"],
                data["staging"],
                domains_to_ask[first_server] == 2,
                cmd_env=env.copy(),
            )
            != 0
        ):
            status = 2
            LOGGER.error(f"Certificate generation failed for domain(s) {domains} ...")
        else:
            status = 1 if status == 0 else status
            LOGGER.info(f"Certificate generation succeeded for domain(s) : {domains}")

        generated_domains.update(domains.split(","))

    # * Generating the wildcards if necessary
    wildcards = WILDCARD_GENERATOR.get_wildcards()
    if wildcards:
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

            # Process different environment types (staging/prod)
            for key, domains in data.items():
                if not domains:
                    continue

                staging = key == "staging"
                LOGGER.info(
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
                    certbot_new(
                        "dns",
                        domains,
                        email,
                        provider,
                        credentials_file,
                        "default",
                        profile,
                        staging,
                        domains_to_ask[base_domain] == 2,
                        env.copy(),
                    )
                    != 0
                ):
                    status = 2
                    LOGGER.error(f"Certificate generation failed for domain(s) {domains} ...")
                else:
                    status = 1 if status == 0 else status
                    LOGGER.info(f"Certificate generation succeeded for domain(s): {domains}")

                generated_domains.update(domains_split)
    else:
        LOGGER.info("No wildcard domains found, skipping wildcard certificate(s) generation...")

    # * Clearing all missing credentials files
    for file in CACHE_PATH.rglob("*"):
        if "etc" in file.parts or not file.is_file() or file.suffix not in (".ini", ".env", ".json"):
            continue
        # ? If the file is not in the wildcard groups, remove it
        if file not in credential_paths:
            LOGGER.debug(f"Removing old credentials file {file}")
            JOB.del_cache(file.name, job_name="certbot-renew", service_id=file.parent.name if file.parent.name != "letsencrypt" else "")

    # * Clearing all no longer needed certificates
    if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
        LOGGER.info("Clear old certificates is activated, removing old / no longer used certificates...")

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
            for block in certificate_blocks:
                cert_name = block.split("\n", 1)[0].strip()

                # Skip certificates that are in our active list
                if cert_name in active_cert_names:
                    LOGGER.debug(f"Keeping active certificate: {cert_name}")
                    continue

                LOGGER.warning(f"Removing old certificate {cert_name} (not in active certificates list)")

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
                    LOGGER.info(f"Successfully deleted certificate {cert_name}")
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
                                        LOGGER.error(f"Failed to remove file {file}: {e}")
                                path.rmdir()
                                LOGGER.info(f"Removed directory {path}")
                            except Exception as e:
                                LOGGER.error(f"Failed to remove directory {path}: {e}")
                        if renewal_file.exists():
                            try:
                                renewal_file.unlink()
                                LOGGER.info(f"Removed renewal file {renewal_file}")
                            except Exception as e:
                                LOGGER.error(f"Failed to remove renewal file {renewal_file}: {e}")
                else:
                    LOGGER.error(f"Failed to delete certificate {cert_name}: {delete_proc.stdout}")
        else:
            LOGGER.error(f"Error listing certificates: {proc.stdout}")

    # * Save data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH, job_name="certbot-renew")
        if not cached:
            LOGGER.error(f"Error while saving data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved data to db cache")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-new.py :\n{e}")

sys_exit(status)
