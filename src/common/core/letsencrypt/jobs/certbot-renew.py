#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from subprocess import DEVNULL, PIPE, Popen, run
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
        stdout=PIPE,
        stderr=PIPE,
        universal_newlines=True,
        env=cmd_env,
    )
    stdout, stderr = process.communicate()
    if stdout:
        for line in stdout.splitlines():
            line_str = line.strip()
            if line_str:
                LOGGER_CERTBOT.info(line_str)
                if "(success)" in line_str or "Congratulations" in line_str:
                    status = 1
    if stderr:
        for line in stderr.splitlines():
            LOGGER_CERTBOT.info(line.strip())

    if process.returncode != 0:
        status = 2
        LOGGER.error("Certificates renewal failed")

    # Save Let's Encrypt data to db cache (full directory)
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH)
        if not cached:
            LOGGER.error(f"Error while saving Let's Encrypt data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved Let's Encrypt data to db cache")

    # Trigger OCSP refresh after successful renewal (AFTER database save)
    # OCSP job will compare new certs with cached ones and process differential updates
    if status == 1 and getenv("SSL_USE_OCSP_STAPLING", "yes").lower() == "yes":
        LOGGER.info("🔄 OCSP triggering refresh for renewed certificates")

        try:
            import sys

            ocsp_script = join(sep, "usr", "share", "bunkerweb", "core", "ssl", "jobs", "ocsp-refresh.py")
            result = run([sys.executable, ocsp_script, "--force"], stdin=DEVNULL, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                LOGGER.info("✓ OCSP refresh completed successfully after renewal")
            else:
                LOGGER.warning(f"⚠️ OCSP refresh returned exit code {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    LOGGER.debug(f"OCSP: {line}")
        except Exception as e:
            LOGGER.warning(f"⚠️ OCSP post-renewal refresh failed (non-fatal): {e}")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-renew.py :\n{e}")

sys_exit(status)
