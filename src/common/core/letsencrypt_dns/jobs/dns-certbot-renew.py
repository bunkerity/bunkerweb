#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("LETS-ENCRYPT-DNS.renew", getenv("LOG_LEVEL", "INFO"))
LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT-DNS.renew.certbot", getenv("LOG_LEVEL", "INFO"))
status = 0

LIB_PATH = Path(sep, "var", "lib", "bunkerweb", "letsencrypt_dns")
PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt_dns")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
DATA_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt_dns", "etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt_dns")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt_dns")

deps_path = LIB_PATH.joinpath("python")
CERTBOT_BIN = deps_path.joinpath("bin", "certbot")

try:
    # Check if we're using let's encrypt
    use_letsencrypt_dns = False
    if not getenv("MULTISITE", "no") == "yes":
        use_letsencrypt_dns = getenv("AUTO_LETS_ENCRYPT_DNS", "no") == "yes"
    else:
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT_DNS", "no") == "yes":
                use_letsencrypt_dns = True
                break

    if not use_letsencrypt_dns:
        LOGGER.info("Let's Encrypt DNS is not activated, skipping generation...")
        sys_exit(0)
    elif not CERTBOT_BIN.is_file():
        LOGGER.error("Additional dependencies not installed, skipping certificate(s) generation...")
        sys_exit(2)

    JOB = Job(LOGGER)

    process = Popen(
        [
            CERTBOT_BIN,
            "renew",
            "--no-random-sleep-on-renew",
            "--config-dir",
            DATA_PATH.as_posix(),
            "--work-dir",
            WORK_DIR,
            "--logs-dir",
            LOGS_DIR,
        ],
        stdin=DEVNULL,
        stderr=PIPE,
        universal_newlines=True,
        env=environ | {"PYTHONPATH": deps_path.as_posix()},
    )
    while process.poll() is None:
        if process.stderr:
            for line in process.stderr:
                LOGGER_CERTBOT.info(line.strip())

    if process.returncode != 0:
        status = 2
        LOGGER.error("Certificates renewal failed")

    # Save Let's Encrypt DNS data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH)
        if not cached:
            LOGGER.error(f"Error while saving Let's Encrypt DNS data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved Let's Encrypt DNS data to db cache")
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running certbot-renew.py :\n{format_exc()}")

sys_exit(status)
