#!/usr/bin/env python3

from os import W_OK, access, environ, getenv, sep, umask
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("LETS-ENCRYPT.RENEW")
LIB_PATH = Path(sep, "var", "lib", "bunkerweb", "letsencrypt")
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

LOGGER_CERTBOT = getLogger("LETS-ENCRYPT.RENEW.CERTBOT")
status = 0

CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")


def prepare_logs_dir() -> None:
    """Ensure the Let's Encrypt logs directory is writable by the running user.

    Old installations could leave `letsencrypt.log` owned by root with 640
    permissions, blocking renewals executed as a non-root user. We normalise the
    directory permissions, drop the umask to keep group write access, and remove
    any stale, non-writable log files so certbot can recreate them.
    """

    # Allow group write on newly created files
    try:
        umask(0o007)
    except BaseException:
        LOGGER.debug("Failed to set umask to 007 for letsencrypt logs")

    logs_path = Path(LOGS_DIR)

    try:
        logs_path.mkdir(parents=True, exist_ok=True)
    except BaseException as e:
        LOGGER.error(f"Failed to create Let's Encrypt logs directory {logs_path}: {e}")
        return

    try:
        logs_path.chmod(0o2770)
    except BaseException as e:
        LOGGER.debug(f"Failed to set permissions on {logs_path}: {e}")

    for log_file in logs_path.glob("*.log*"):
        try:
            if access(log_file, W_OK):
                log_file.chmod(0o660)
            else:
                LOGGER.warning(f"Removing unwritable Let's Encrypt log file {log_file}")
                log_file.unlink(missing_ok=True)
        except BaseException as e:
            LOGGER.debug(f"Failed to adjust permissions on log file {log_file}: {e}")


try:
    # Check if we're using let's encrypt
    use_letsencrypt = False

    if getenv("MULTISITE", "no") == "no":
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
    else:
        for first_server in getenv("SERVER_NAME", "www.example.com").split(" "):
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True
                break

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping renew...")
        sys_exit(0)

    prepare_logs_dir()

    JOB = Job(LOGGER, __file__)

    cmd_env = environ.copy()

    db_config = JOB.db.get_config()
    for key in db_config:
        if key in cmd_env:
            del cmd_env[key]

    cmd_env["PYTHONPATH"] = cmd_env["PYTHONPATH"] + (f":{DEPS_PATH}" if DEPS_PATH not in cmd_env["PYTHONPATH"] else "")
    if getenv("DATABASE_URI", ""):
        cmd_env["DATABASE_URI"] = getenv("DATABASE_URI", "")

    process = Popen(
        [
            CERTBOT_BIN,
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
