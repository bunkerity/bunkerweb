#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from copy import deepcopy
from datetime import datetime, timedelta
from itertools import chain
from json import dumps
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, search
from select import select
from shutil import rmtree
from subprocess import DEVNULL, PIPE, STDOUT, Popen, run
from sys import exit as sys_exit, path as sys_path
from typing import Dict, Literal, Type, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from pydantic import ValidationError
from letsencrypt import (
    CloudflareProvider,
    DigitalOceanProvider,
    DnsimpleProvider,
    DnsMadeEasyProvider,
    GehirnProvider,
    GoogleProvider,
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

LOGGER = setup_logger("LETS-ENCRYPT.new", getenv("LOG_LEVEL", "INFO"))
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT.new.certbot", getenv("LOG_LEVEL", "INFO"))
status = 0

PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")


def certbot_new(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: str = None,
    credentials_path: Union[str, Path] = None,
    propagation: str = "default",
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

        # * Adding plugin argument
        if provider == "scaleway":
            # ? Scaleway plugin uses different arguments
            command.extend(["--authenticator", "dns-scaleway"])
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
                Type[DigitalOceanProvider],
                Type[DnsimpleProvider],
                Type[DnsMadeEasyProvider],
                Type[GehirnProvider],
                Type[GoogleProvider],
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
            "digitalocean": DigitalOceanProvider,
            "dnsimple": DnsimpleProvider,
            "dnsmadeeasy": DnsMadeEasyProvider,
            "gehirn": GehirnProvider,
            "google": GoogleProvider,
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
                wildcards = WildcardGenerator.get_wildcards_from_domains((first_server,))
                first_server = wildcards[0].lstrip("*.")
                domains = set(wildcards)
            else:
                domains = set(domains.split(" "))

            certificate_block = None
            for block in certificate_blocks:
                if block.startswith(f"{first_server}\n"):
                    certificate_block = block
                    break

            if not certificate_block:
                domains_to_ask[first_server] = True
                LOGGER.warning(f"[{original_first_server}] Certificate block for {first_server} not found, asking new certificate...")
                continue

            try:
                cert_domains = search(r"Domains: (?P<domains>.*)\n\s*Expiry Date: (?P<expiry_date>.*)\n", certificate_block, MULTILINE)
            except Exception as e:
                LOGGER.error(f"[{original_first_server}] Error while parsing certificate block: {e}")
                continue

            if not cert_domains:
                LOGGER.error(f"[{original_first_server}] Failed to parse domains and expiry date from certificate block.")
                continue

            cert_domains_list = cert_domains.group("domains").strip().split()
            cert_domains_set = set(cert_domains_list)

            if cert_domains_set != domains:
                domains_to_ask[first_server] = True
                LOGGER.warning(f"[{original_first_server}] Domains for {first_server} are not the same as in the certificate, asking new certificate...")
                continue

            use_letsencrypt_staging = getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes"
            is_test_cert = "TEST_CERT" in cert_domains.group("expiry_date")

            if (is_test_cert and not use_letsencrypt_staging) or (not is_test_cert and use_letsencrypt_staging):
                domains_to_ask[first_server] = True
                LOGGER.warning(f"[{original_first_server}] Certificate environment (staging/production) changed for {first_server}, asking new certificate...")
                continue

            letsencrypt_provider = getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER", getenv("LETS_ENCRYPT_DNS_PROVIDER", ""))

            renewal_file = DATA_PATH.joinpath("renewal", f"{first_server}.conf")
            if not renewal_file.is_file():
                LOGGER.error(f"[{original_first_server}] Renewal file for {first_server} not found, asking new certificate...")
                domains_to_ask[first_server] = True
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
                    domains_to_ask[first_server] = True
                    LOGGER.warning(f"[{original_first_server}] Provider for {first_server} is not the same as in the certificate, asking new certificate...")
                    continue
            elif current_provider != "manual" and letsencrypt_challenge == "http":
                domains_to_ask[first_server] = True
                LOGGER.warning(f"[{original_first_server}] {first_server} is no longer using DNS challenge, asking new certificate...")
                continue

            domains_to_ask[first_server] = False
            LOGGER.info(f"[{original_first_server}] Certificates already exist for domain(s) {domains}, expiry date: {cert_domains.group('expiry_date')}")

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
            "credential_items": {},
        }

        if data["challenge"] == "http" and data["use_wildcard"]:
            LOGGER.warning(f"Wildcard is not supported with HTTP challenge, disabling wildcard for service {first_server}...")
            data["use_wildcard"] = False

        if (not data["use_wildcard"] and not domains_to_ask.get(first_server)) or (
            data["use_wildcard"] and not domains_to_ask.get(WILDCARD_GENERATOR.get_wildcards_from_domains((first_server,))[0].lstrip("*."))
        ):
            continue

        # * Getting the DNS provider data if necessary
        if data["challenge"] == "dns":
            credential_key = f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" if IS_MULTISITE else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
            for env_key, env_value in environ.items():
                if env_value and env_key.startswith(credential_key):
                    key, value = env_value.split(" ", 1)
                    data["credential_items"][key.lower()] = value

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
                LOGGER.warning(f"No credentials items found for service {first_server} (you should have at least one), skipping certificate(s) generation...")
                continue

            # * Validating the credentials
            try:
                provider = provider_classes[data["provider"]](**data["credential_items"])
            except ValidationError as ve:
                LOGGER.error(f"Error while validating credentials for service {first_server} :\n{ve}")
                continue

            content = provider.get_formatted_credentials()
        else:
            content = b"http_challenge"

        # * Adding the domains to Wildcard Generator if necessary
        file_type = provider.get_file_type() if data["challenge"] == "dns" else "txt"
        file_path = (first_server, f"credentials.{file_type}")
        if data["use_wildcard"]:
            group = f"{data['provider'] if data['challenge'] == 'dns' else 'http'}_{bytes_hash(content, algorithm='sha1')}"
            LOGGER.info(
                f"Service {first_server} is using wildcard, "
                + ("the propagation time will be the provider's default and " if data["challenge"] == "dns" else "")
                + "the email will be the same as the first domain that created the group..."
            )
            WILDCARD_GENERATOR.extend(group, domains.split(" "), data["email"], data["staging"])
            file_path = (f"{group}.{file_type}",)

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
            f"Asking certificates for domain(s) : {domains} (email = {data['email']}){' using staging' if data['staging'] else ''} with {data['challenge']} challenge..."
        )
        if (
            certbot_new(
                data["challenge"],
                domains,
                data["email"],
                data["provider"],
                credentials_path,
                data["propagation"],
                data["staging"],
                domains_to_ask[first_server],
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
            provider = group.split("_", 1)[0]

            email = data.pop("email")
            credentials_file = CACHE_PATH.joinpath(f"{group}.{provider_classes[provider].get_file_type() if provider in provider_classes else 'txt'}")
            for key, domains in data.items():
                if not domains:
                    continue

                staging = key == "staging"
                LOGGER.info(
                    f"Asking wildcard certificates for domain(s) : {domains} (email = {email}){' using staging ' if staging else ''} with {'dns' if provider in provider_classes else 'http'} challenge..."
                )
                if (
                    certbot_new(
                        "dns" if provider in provider_classes else "http",
                        domains,
                        email,
                        provider,
                        credentials_file,
                        staging=staging,
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
    else:
        LOGGER.info("No wildcard domains found, skipping wildcard certificate(s) generation...")

    # * Clearing all missing credentials files
    for file in CACHE_PATH.glob("**/*"):
        if "etc" in file.parts or not file.is_file() or file.suffix not in (".ini", ".env", ".json"):
            continue
        # ? If the file is not in the wildcard groups, remove it
        if file not in credential_paths:
            LOGGER.debug(f"Removing old credentials file {file}")
            JOB.del_cache(file.name, job_name="certbot-renew", service_id=file.parent.name if file.parent.name != "letsencrypt" else "")

    # * Clearing all no longer needed certificates
    if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
        LOGGER.info("Clear old certificates is activated, removing old / no longer used certificates...")
        for elem in chain(DATA_PATH.glob("archive/*"), DATA_PATH.glob("live/*"), DATA_PATH.glob("renewal/*")):
            cert_name = elem.name.replace(".conf", "")
            if cert_name not in generated_domains and cert_name not in domains_to_ask and elem.name != "README":
                LOGGER.warning(f"Removing old certificate {elem}")
                if elem.is_dir():
                    rmtree(elem, ignore_errors=True)
                else:
                    elem.unlink(missing_ok=True)

    # * Save data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH, job_name="certbot-renew")
        if not cached:
            LOGGER.error(f"Error while saving data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved data to db cache")
except SystemExit as e:
    status = e.code
except:
    status = 1
    LOGGER.exception("Exception while running certbot-new.py")

sys_exit(status)
