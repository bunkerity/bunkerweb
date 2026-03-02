#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, TimeoutExpired
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore
from letsencrypt_utils import (
    CERTBOT_BIN,
    DEPS_PATH,
    LETSENCRYPT_DATA_PATH as DATA_PATH,
    LETSENCRYPT_LOGS_DIR as LOGS_DIR,
    LETSENCRYPT_WORK_DIR as WORK_DIR,
    ZEROSSL_BOT_SCRIPT,
    build_certbot_env,
    is_zerossl_used_in_env,
    prepare_logs_dir,
    resolve_certbot_entrypoint,
    run_process_with_timeout,
    update_renewal_config_authenticator,
)

LOGGER = getLogger("LETS-ENCRYPT.RENEW")

LOGGER_CERTBOT = getLogger("LETS-ENCRYPT.RENEW.CERTBOT")
status = 0

try:
    # Check if we're using let's encrypt
    use_letsencrypt = False

    if getenv("MULTISITE", "no") == "no":
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
    else:
        for first_server in getenv("SERVER_NAME", "www.example.com").split():
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True
                break

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping renew...")
        sys_exit(0)

    prepare_logs_dir(LOGS_DIR, LOGGER)

    JOB = Job(LOGGER, __file__)

    cmd_env = build_certbot_env(JOB, DEPS_PATH)
    acme_server = "zerossl" if is_zerossl_used_in_env() else "letsencrypt"
    certbot_entrypoint = resolve_certbot_entrypoint(
        acme_server,
        CERTBOT_BIN,
        ZEROSSL_BOT_SCRIPT,
        LOGGER,
        cmd_env=cmd_env,
        fallback_to_certbot=True,
    )
    certbot_bin = certbot_entrypoint[0]
    if acme_server == "zerossl" and certbot_bin != CERTBOT_BIN:
        LOGGER.info("Using zerossl-bot wrapper for certificate renewal.")

    # Update renewal configs if challenge type or DNS provider has changed
    renewal_conf_dir = DATA_PATH / "renewal"
    if renewal_conf_dir.is_dir():
        for conf_file in renewal_conf_dir.glob("*.conf"):
            domain = conf_file.stem
            try:
                # Determine new authenticator based on current settings
                if getenv("MULTISITE", "no") == "yes":
                    challenge = getenv(f"{domain}_LETS_ENCRYPT_CHALLENGE", getenv("LETS_ENCRYPT_CHALLENGE", "http")).lower()
                    dns_provider = getenv(f"{domain}_LETS_ENCRYPT_DNS_PROVIDER", getenv("LETS_ENCRYPT_DNS_PROVIDER", "")).lower()
                else:
                    challenge = getenv("LETS_ENCRYPT_CHALLENGE", "http").lower()
                    dns_provider = getenv("LETS_ENCRYPT_DNS_PROVIDER", "").lower()

                if challenge == "dns" and dns_provider:
                    new_authenticator = f"dns-{dns_provider}"
                else:
                    new_authenticator = "webroot"

                update_renewal_config_authenticator(renewal_conf_dir, domain, new_authenticator, LOGGER)
            except BaseException as e:
                LOGGER.debug(f"Failed to update renewal config for {domain}: {e}")

    command = [
        certbot_bin,
        "renew",
        "-n",
        "--no-random-sleep-on-renew",
        "--config-dir",
        DATA_PATH.as_posix(),
        "--work-dir",
        WORK_DIR,
        "--logs-dir",
        LOGS_DIR,
    ]
    if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG":
        command.append("-v")

    try:
        returncode = run_process_with_timeout(command, 360, LOGGER_CERTBOT, cmd_env)
        if returncode != 0:
            status = 2
            LOGGER.error("Certificates renewal failed")
    except TimeoutExpired:
        status = 2
        LOGGER.error("Certificates renewal exceeded 6 minute timeout")

    # Save Let's Encrypt data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH)
        if not cached:
            LOGGER.error(f"Error while saving Let's Encrypt data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved Let's Encrypt data to db cache")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-renew.py :\n{e}")

sys_exit(status)
