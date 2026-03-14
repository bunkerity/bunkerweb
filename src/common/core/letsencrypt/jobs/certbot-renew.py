#!/usr/bin/env python3

import importlib.util
from os import getenv, sep
from os.path import dirname, join
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen
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
    remove_empty_renewal_configs,
    repair_live_symlinks,
    resolve_certbot_entrypoint,
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

    # Repair live/ symlinks first (avoids certbot "expected to be a symlink"), then remove broken renewal configs.
    # Broken = empty, unparseable, or missing required file reference. Reissue uses service definitions from env.
    removed_empty_configs: list = []
    if DATA_PATH.is_dir():
        repair_live_symlinks(DATA_PATH, LOGGER)
        removed_empty_configs = remove_empty_renewal_configs(DATA_PATH, LOGGER)

    cmd_env = build_certbot_env(JOB, DEPS_PATH)

    # certbot-new is scheduled as "every: once" (init-only), while certbot-renew is periodic.
    # If we removed a broken renewal config, trigger reissue now using service definitions from env (not the bad file).
    if removed_empty_configs:
        certbot_new_path = Path(dirname(__file__)).resolve() / "certbot-new.py"
        spec = importlib.util.spec_from_file_location("certbot_new", certbot_new_path)
        certbot_new_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(certbot_new_mod)
        if not certbot_new_mod.reissue_for_removed_configs(removed_empty_configs, JOB, cmd_env, LOGGER):
            status = 2
            LOGGER.error("Reissue after removing broken renewal config(s) failed")
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

    process = Popen(
        [
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
        + (["-v"] if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG" else []),
        stdin=DEVNULL,
        stderr=PIPE,
        universal_newlines=True,
        env=cmd_env,
    )
    while process.poll() is None:
        if process.stderr:
            for line in process.stderr:
                LOGGER_CERTBOT.info(line.strip())

    if process.returncode != 0:
        status = 2
        LOGGER.error("Certificates renewal failed")

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
