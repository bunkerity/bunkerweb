#!/usr/bin/python3

from os import environ, getenv, listdir
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from tarfile import open as tfopen
from io import BytesIO
from shutil import rmtree

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/db",
    )
)

from logger import setup_logger
from Database import Database
from jobs import get_file_in_db, set_file_in_db


def renew(domain):
    environ["PYTHONPATH"] = "/usr/share/bunkerweb/deps/python"
    proc = run(
        [
            "/usr/share/bunkerweb/deps/python/bin/certbot",
            "renew",
            "--config-dir=/var/cache/bunkerweb/letsencrypt/etc",
            "--work-dir=/var/cache/bunkerweb/letsencrypt/lib",
            "--logs-dir=/var/cache/bunkerweb/letsencrypt/log",
            "--cert-name",
            domain,
            "--deploy-hook",
            "/usr/share/bunkerweb/core/letsencrypt/jobs/certbot-deploy.py",
        ],
        stdin=DEVNULL,
        stderr=STDOUT,
        env=environ,
    )
    return proc.returncode


logger = setup_logger("LETS-ENCRYPT.renew", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Create directory if it doesn't exist
    Path("/var/cache/bunkerweb/letsencrypt").mkdir(parents=True, exist_ok=True)

    # Extract letsencrypt folder if it exists in db
    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    if db:
        tgz = get_file_in_db("folder.tgz", db)
        if tgz:
            # Delete folder if needed
            if len(listdir("/var/cache/bunkerweb/letsencrypt")) > 0:
                rmtree("/var/cache/bunkerweb/letsencrypt", ignore_errors=True)
            # Extract it
            with tfopen(name="folder.tgz", mode="r:gz", fileobj=BytesIO(tgz)) as tf:
                tf.extractall("/var/cache/bunkerweb/letsencrypt")
            logger.info("Successfully retrieved Let's Encrypt data from db cache")
        else:
            logger.info("No Let's Encrypt data found in db cache")

    if getenv("MULTISITE") == "yes":
        servers = getenv("SERVER_NAME", [])

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if (
                not first_server
                or getenv(
                    f"{first_server}_AUTO_LETS_ENCRYPT",
                    getenv("AUTO_LETS_ENCRYPT", "no"),
                )
                != "yes"
                or not Path(
                    f"/var/cache/bunkerweb/letsencrypt/etc/live/{first_server}/cert.pem"
                ).exists()
            ):
                continue

            ret = renew(first_server)
            if ret != 0:
                status = 2
                logger.error(
                    f"Certificates renewal for {first_server} failed",
                )
    elif getenv("AUTO_LETS_ENCRYPT", "no") == "yes" and not getenv("SERVER_NAME", ""):
        first_server = getenv("SERVER_NAME", "").split(" ")[0]
        if Path(
            f"/var/cache/bunkerweb/letsencrypt/etc/live/{first_server}/cert.pem"
        ).exists():
            ret = renew(first_server)
            if ret != 0:
                status = 2
                logger.error(
                    f"Certificates renewal for {first_server} failed",
                )

    # Put new folder in cache
    if db:
        bio = BytesIO()
        with tfopen("folder.tgz", mode="w:gz", fileobj=bio) as tgz:
            tgz.add("/var/cache/bunkerweb/letsencrypt", arcname=".")
        bio.seek(0)
        # Put tgz in cache
        cached, err = set_file_in_db("folder.tgz", bio, db)
        if not cached:
            logger.error(f"Error while saving Let's Encrypt data to db cache : {err}")
        else:
            logger.info("Successfully saved Let's Encrypt data to db cache")
        # Delete lib and log folders to avoid sending them
        if Path("/var/cache/bunkerweb/letsencrypt/lib").exists():
            rmtree("/var/cache/bunkerweb/letsencrypt/lib", ignore_errors=True)
        if Path("/var/cache/bunkerweb/letsencrypt/log").exists():
            rmtree("/var/cache/bunkerweb/letsencrypt/log", ignore_errors=True)

except:
    status = 2
    logger.error(f"Exception while running certbot-renew.py :\n{format_exc()}")

sys_exit(status)
