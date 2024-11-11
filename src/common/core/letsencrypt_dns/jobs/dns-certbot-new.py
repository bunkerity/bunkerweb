#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from itertools import chain
from json import dumps
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from subprocess import DEVNULL, STDOUT, Popen
from sys import exit as sys_exit, path as sys_path
from typing import Dict, List, Literal, Type, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("LETS-ENCRYPT-DNS.new", getenv("LOG_LEVEL", "INFO"))
LIB_PATH = Path(sep, "var", "lib", "bunkerweb", "letsencrypt_dns")

deps_path = LIB_PATH.joinpath("python").as_posix()
if deps_path not in sys_path:
    sys_path.append(deps_path)

CERTBOT_BIN = LIB_PATH.joinpath("python", "bin", "certbot")

LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT-DNS.new.certbot", getenv("LOG_LEVEL", "INFO"))
status = 0

PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt_dns")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt_dns")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt_dns")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt_dns")


class WildcardGenerator:
    def __init__(self):
        self.__domain_groups = {}
        self.__wildcards = {}

    def __generate_wildcards(self, staging: bool = False):
        self.__wildcards.clear()
        _type = "staging" if staging else "prod"

        # * Loop through all the domains and generate wildcards
        for group, types in self.__domain_groups.items():
            if group not in self.__wildcards:
                self.__wildcards[group] = {"staging": set(), "prod": set(), "email": types["email"]}
            for domain in types[_type]:
                parts = domain.split(".")
                # ? Only take subdomains into account for wildcards generation
                if len(parts) > 2:
                    suffix = ".".join(parts[1:])
                    # ? If the suffix is not already in the wildcards, add it
                    if suffix not in self.__wildcards[group][_type]:
                        self.__wildcards[group][_type].add(f"*.{suffix}")
                        self.__wildcards[group][_type].add(suffix)
                    continue

                # ? Add the raw domain to the wildcards
                self.__wildcards[group][_type].add(domain)

    def extend(self, group: str, domains: List[str], email: str, staging: bool = False):
        if group not in self.__domain_groups:
            self.__domain_groups[group] = {"staging": set(), "prod": set(), "email": email}
        for domain in domains:
            if domain := domain.strip():
                self.__domain_groups[group]["staging" if staging else "prod"].add(domain)
        self.__generate_wildcards(staging)

    def get_wildcards(self) -> Dict[str, Dict[Literal["staging", "prod", "email"], str]]:
        ret_data = {}
        for group, data in self.__wildcards.items():
            ret_data[group] = {"email": data["email"]}
            for _type, content in data.items():
                if _type in ("staging", "prod"):
                    # ? Sort domains while favoring wildcards first
                    ret_data[group][_type] = ",".join(sorted(content, key=lambda x: x[0] != "*"))
        return ret_data


def certbot_new(provider: str, credentials_path: Union[str, Path], domains: str, email: str, propagation: str = "default", staging: bool = False) -> int:
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
        "--preferred-challenges=dns",
        "-n",
        "-d",
        domains,
        "--email",
        email,
        "--agree-tos",
        "--expand",
    ]

    # * Adding the propagation time to the command
    if propagation != "default":
        if not propagation.isdigit():
            LOGGER.warning(f"Invalid propagation time : {propagation}, using provider's default...")
        else:
            command.extend([f"--dns-{provider}-propagation-seconds", propagation])

    env = environ | {"PYTHONPATH": deps_path}

    # * Adding the credentials to the command
    if provider == "route53":
        # ? Route53 credentials are different from the others, we need to add them to the environment
        with credentials_path.open("r") as file:
            for line in file:
                key, value = line.strip().split("=", 1)
                env[key] = value
    else:
        command.extend([f"--dns-{provider}-credentials", credentials_path.as_posix()])

    # * Adding plugin argument
    if provider == "scaleway":
        # ? Scaleway plugin uses a different argument
        command.extend(["--authenticator", "dns-scaleway"])
    else:
        command.append(f"--dns-{provider}")

    if staging:
        command.append("--staging")

    current_date = datetime.now()
    process = Popen(command, stdin=DEVNULL, stderr=STDOUT, universal_newlines=True, env=env)
    while process.poll() is None:
        if datetime.now() - current_date > timedelta(seconds=5):
            LOGGER.info("⏳ Still generating certificate(s)...")
            current_date = datetime.now()
    return process.returncode


IS_MULTISITE = getenv("MULTISITE", "no") == "yes"

try:
    servers = getenv("SERVER_NAME", "").lower() or []

    if isinstance(servers, str):
        servers = servers.split(" ")

    if not servers:
        LOGGER.error("There are no server names, skipping generation...")
        sys_exit(0)

    use_letsencrypt_dns = False
    if not IS_MULTISITE:
        servers = [servers[0]]
        use_letsencrypt_dns = getenv("AUTO_LETS_ENCRYPT_DNS", "no") == "yes"
    else:
        for first_server in servers:
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT_DNS", "no") == "yes":
                use_letsencrypt_dns = True
                break

    if not use_letsencrypt_dns:
        LOGGER.info("Let's Encrypt DNS is not activated, skipping generation...")
        sys_exit(0)
    elif not CERTBOT_BIN.is_file():
        LOGGER.error("Additional dependencies not installed, skipping certificate(s) generation...")
        sys_exit(2)

    from pydantic import ValidationError
    from models import (
        CloudflareProvider,
        DigitalOceanProvider,
        GoogleProvider,
        LinodeProvider,
        OvhProvider,
        Rfc2136Provider,
        Route53Provider,
        ScalewayProvider,
    )

    PROVIDER_CLASSES: Dict[
        str,
        Union[
            Type[CloudflareProvider],
            Type[DigitalOceanProvider],
            Type[GoogleProvider],
            Type[LinodeProvider],
            Type[OvhProvider],
            Type[Rfc2136Provider],
            Type[Route53Provider],
            Type[ScalewayProvider],
        ],
    ] = {
        "cloudflare": CloudflareProvider,
        "digitalocean": DigitalOceanProvider,
        "google": GoogleProvider,
        "linode": LinodeProvider,
        "ovh": OvhProvider,
        "rfc2136": Rfc2136Provider,
        "route53": Route53Provider,
        "scaleway": ScalewayProvider,
    }

    JOB = Job(LOGGER)

    # ? Restore data from db cache of dns-certbot-renew job
    JOB.restore_cache(job_name="dns-certbot-renew")

    WILDCARD_GENERATOR = WildcardGenerator()
    credential_paths = set()
    generated_domains = set()

    for first_server in servers:
        if getenv(f"{first_server}_AUTO_LETS_ENCRYPT_DNS", getenv("AUTO_LETS_ENCRYPT_DNS", "no")) == "no":
            LOGGER.info(f"Skipping certificate(s) generation for {first_server} because it is not enabled")
            continue
        elif getenv(f"{first_server}_AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) == "yes":
            LOGGER.warning(f"Skipping certificate(s) generation for {first_server} because it is using regular Let's Encrypt")
            continue

        # * Getting all the necessary data
        data = {
            "domains": getenv(f"{first_server}_SERVER_NAME", getenv("SERVER_NAME", "")).lower() or first_server,
            "email": getenv(f"{first_server}_LETS_ENCRYPT_DNS_EMAIL", getenv("LETS_ENCRYPT_DNS_EMAIL", "")) or f"contact@{first_server}",
            "staging": getenv(f"{first_server}_USE_LETS_ENCRYPT_DNS_STAGING", getenv("USE_LETS_ENCRYPT_DNS_STAGING", "no")) == "yes",
            "provider": getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER", getenv("LETS_ENCRYPT_DNS_PROVIDER", "")),
            "use_wildcard": getenv(f"{first_server}_USE_LETS_ENCRYPT_DNS_WILDCARD", getenv("USE_LETS_ENCRYPT_DNS_WILDCARD", "no")) == "yes",
            "propagation": getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROPAGATION", getenv("LETS_ENCRYPT_DNS_PROPAGATION", "default")),
            "credential_items": {},
        }
        for env_key, env_value in environ.items():
            if env_value and env_key.startswith(f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" if IS_MULTISITE else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"):
                key, value = env_value.split(" ", 1)
                data["credential_items"][key.lower()] = value

        LOGGER.debug(f"Data for service {first_server} : {dumps(data)}")

        # * Checking if the data is valid
        if not data["provider"]:
            LOGGER.warning(
                f"No provider found for service {first_server} (available providers : {', '.join(PROVIDER_CLASSES.keys())}), skipping certificate(s) generation..."  # noqa: E501
            )
            continue
        elif not data["credential_items"]:
            LOGGER.warning(f"No credentials items found for service {first_server} (you should have at least one), skipping certificate(s) generation...")
            continue

        # * Validating the credentials
        try:
            provider = PROVIDER_CLASSES[data["provider"]](**data["credential_items"])
        except ValidationError as ve:
            LOGGER.error(f"Error while validating credentials for service {first_server} :\n{ve}")
            continue

        content = provider.get_formatted_credentials()

        # * Adding the domains to Wildcard Generator if necessary
        file_path = (first_server, f"credentials.{provider.get_file_type()}")
        if data["use_wildcard"]:
            group = f"{data['provider']}_{bytes_hash(content, algorithm='sha1')}"
            LOGGER.info(
                f"Service {first_server} is using wildcard, the propagation time will be the provider's default "
                + "and the email will be the same as the first domain that created the group..."
            )
            WILDCARD_GENERATOR.extend(group, data["domains"].strip().split(" "), data["email"], data["staging"])
            file_path = (f"{group}.{provider.get_file_type()}",)

        # * Generating the credentials file
        credentials_path = CACHE_PATH.joinpath(*file_path)

        if not credentials_path.is_file():
            cached, err = JOB.cache_file(
                credentials_path.name, content, job_name="dns-certbot-renew", service_id=first_server if not data["use_wildcard"] else ""
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
                cached, err = JOB.cache_file(credentials_path.name, content, job_name="dns-certbot-renew", service_id=first_server)
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

        domains = data["domains"].replace(" ", ",")
        LOGGER.info(f"Asking certificates for domain(s) : {domains} (email = {data['email']}) {'using staging ' if data['staging'] else ''}...")
        if certbot_new(data["provider"], credentials_path, domains, data["email"], data["propagation"], data["staging"]) != 0:
            status = 2
            LOGGER.error(f"Certificate generation failed for domain(s) {data['domains']} ...")
        else:
            status = 1 if status == 0 else status
            LOGGER.info(f"Certificate generation succeeded for domain(s) : {data['domains']}")

        generated_domains.update(data["domains"].split(","))

    # * Generating the wildcards if necessary
    wildcards = WILDCARD_GENERATOR.get_wildcards()
    if wildcards:
        for group, data in wildcards.items():
            if not data:
                continue
            # * Generating the certificate from the generated credentials
            provider = group.split("_", 1)[0]
            email = data.pop("email")
            credentials_file = CACHE_PATH.joinpath(f"{group}.{PROVIDER_CLASSES[provider].get_file_type()}")
            for key, domains in data.items():
                if not domains:
                    continue
                staging = key == "staging"
                LOGGER.info(f"Asking wildcard certificates for domain(s) : {domains} (email = {email}) {'using staging ' if staging else ''}...")
                if certbot_new(provider, credentials_file, domains, email, staging=staging) != 0:
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
            JOB.del_cache(file.name, job_name="dns-certbot-renew", service_id=file.parent.name if file.parent.name != "letsencrypt_dns" else "")

    # * Clearing all no longer needed certificates
    if getenv("LETS_ENCRYPT_DNS_CLEAR_OLD_CERTS", "no") == "yes":
        LOGGER.info("Clear old certificates is activated, removing old / no longer used certificates...")
        for elem in chain(DATA_PATH.glob("archive/*"), DATA_PATH.glob("live/*"), DATA_PATH.glob("renewal/*")):
            if elem.name.replace(".conf", "") not in generated_domains and elem.name != "README":
                LOGGER.warning(f"Removing old certificate {elem}")
                if elem.is_dir():
                    rmtree(elem, ignore_errors=True)
                else:
                    elem.unlink(missing_ok=True)

    # * Save data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH, job_name="dns-certbot-renew")
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
