#!/usr/bin/python3

from os import environ, getenv, listdir
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from threading import Lock
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

from Database import Database
from logger import setup_logger
from jobs import get_file_in_db, set_file_in_db

logger = setup_logger("LETS-ENCRYPT.new", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
lock = Lock()
status = 0


def certbot_new(domains, email):
    environ["PYTHONPATH"] = "/usr/share/bunkerweb/deps/python"
    proc = run(
        [
            "/usr/share/bunkerweb/deps/python/bin/certbot",
            "certonly",
            "--config-dir=/var/cache/bunkerweb/letsencrypt/etc",
            "--work-dir=/var/cache/bunkerweb/letsencrypt/lib",
            "--logs-dir=/var/cache/bunkerweb/letsencrypt/log",
            "--manual",
            "--preferred-challenges=http",
            "--manual-auth-hook",
            "/usr/share/bunkerweb/core/letsencrypt/jobs/certbot-auth.py",
            "--manual-cleanup-hook",
            "/usr/share/bunkerweb/core/letsencrypt/jobs/certbot-cleanup.py",
            "-n",
            "-d",
            domains,
            "--email",
            email,
            "--agree-tos",
        ]
        + (["--staging"] if getenv("USE_LETS_ENCRYPT_STAGING", "no") == "yes" else []),
        stdin=DEVNULL,
        stderr=STDOUT,
        env=environ,
    )
    return proc.returncode


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

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if (
                not first_server
                or getenv(
                    f"{first_server}_AUTO_LETS_ENCRYPT",
                    getenv("AUTO_LETS_ENCRYPT", "no"),
                )
                != "yes"
            ):
                continue

            domains = getenv(f"{first_server}_SERVER_NAME", first_server).replace(
                " ", ","
            )

            if Path(
                f"/var/cache/bunkerweb/letsencrypt/{first_server}/cert.pem"
            ).exists():
                logger.info(
                    f"Certificates already exists for domain(s) {domains}",
                )
                continue

            real_email = getenv(
                f"{first_server}_EMAIL_LETS_ENCRYPT",
                getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}"),
            )
            if not real_email:
                real_email = f"contact@{first_server}"

            logger.info(
                f"Asking certificates for domains : {domains} (email = {real_email}) ...",
            )
            if certbot_new(domains, real_email) != 0:
                status = 2
                logger.error(
                    f"Certificate generation failed for domain(s) {domains} ...",
                )
            else:
                status = 1
                logger.info(
                    f"Certificate generation succeeded for domain(s) : {domains}"
                )

    # Singlesite case
    elif getenv("AUTO_LETS_ENCRYPT", "no") == "yes" and getenv("SERVER_NAME"):
        first_server = getenv("SERVER_NAME", "").split(" ")[0]
        domains = getenv("SERVER_NAME", "").replace(" ", ",")

        if Path(
            f"/var/cache/bunkerweb/letsencrypt/etc/live/{first_server}/cert.pem"
        ).exists():
            logger.info(f"Certificates already exists for domain(s) {domains}")
        else:
            real_email = getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}")
            if not real_email:
                real_email = f"contact@{first_server}"

            logger.info(
                f"Asking certificates for domain(s) : {domains} (email = {real_email}) ...",
            )
            if certbot_new(domains, real_email) != 0:
                status = 2
                logger.error(f"Certificate generation failed for domain(s) : {domains}")
            else:
                status = 1
                logger.info(
                    f"Certificate generation succeeded for domain(s) : {domains}"
                )

    # Put new folder in cache
    if db:
        bio = BytesIO()
        with tfopen("folder.tgz", mode="w:gz", fileobj=bio) as tgz:
            tgz.add("/var/cache/bunkerweb/letsencrypt", arcname=".")
        bio.seek(0)
        # Put tgz in cache
        cached, err = set_file_in_db(f"folder.tgz", bio, db)
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
    status = 3
    logger.error(f"Exception while running certbot-new.py :\n{format_exc()}")

sys_exit(status)
