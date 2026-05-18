#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from subprocess import DEVNULL, PIPE, Popen
from sys import exit as sys_exit, path as sys_path
from time import monotonic
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
    certbot_log_backup_flags,
    is_zerossl_used_in_env,
    prepare_logs_dir,
    resolve_certbot_entrypoint,
)

LOGGER = getLogger("LETS-ENCRYPT.RENEW")

LOGGER_CERTBOT = getLogger("LETS-ENCRYPT.RENEW.CERTBOT")
CERTBOT_TIMEOUT = 900  # 15 minutes max for a single certbot invocation
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
            *certbot_log_backup_flags(cmd_env),
        ]
        + (["-v"] if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG" else []),
        stdin=DEVNULL,
        stderr=PIPE,
        universal_newlines=True,
        env=cmd_env,
    )
    deadline = monotonic() + CERTBOT_TIMEOUT
    while process.poll() is None:
        if monotonic() > deadline:
            LOGGER.error(f"certbot renew timed out after {CERTBOT_TIMEOUT}s, killing process.")
            process.kill()
            process.wait()
            status = 2
            break
        if process.stderr:
            for line in process.stderr:
                LOGGER_CERTBOT.info(line.strip())

    if process.returncode and process.returncode != 0:
        status = 2
        LOGGER.error("Certificates renewal failed")

    # Save Let's Encrypt data to db cache.
    # Guards: only re-cache if the initial restore succeeded AND we actually have live
    # certs on disk. Without these guards, a failed restore leaves DATA_PATH empty
    # (rmtree runs before extraction in Job.restore_cache) and a blind cache_dir() call
    # would overwrite the good DB row with the empty post-rmtree state, losing the certs
    # from both disk and DB.
    if not JOB.restore_ok:
        LOGGER.error("Skipping db cache update: initial cache restore failed, refusing to overwrite good DB state with current disk state.")
        status = 2
    elif not DATA_PATH.is_dir() or not any(DATA_PATH.glob("live/*/fullchain.pem")):
        LOGGER.warning("Skipping db cache update: no live certificates found under DATA_PATH/live/*/fullchain.pem.")
    else:
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
