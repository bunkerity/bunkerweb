#!/usr/bin/python3

from os import environ, getcwd, getenv
from os.path import exists
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/usr/share/bunkerweb/deps/python")
sys_path.append("/usr/share/bunkerweb/utils")
sys_path.append("/usr/share/bunkerweb/db")

from Database import Database
from logger import setup_logger

logger = setup_logger("LETS-ENCRYPT", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
status = 0


def certbot_new(domains, email):
    environ["PYTHONPATH"] = "/usr/share/bunkerweb/deps/python"
    proc = run(
        [
            "/usr/share/bunkerweb/deps/python/bin/certbot certonly",
            "--manual",
            "--preferred-challenges=http",
            "--manual-auth-hook",
            f"{getcwd()}/certbot-auth.py",
            "--manual-cleanup-hook",
            f"{getcwd()}/certbot-cleanup.py",
            "-n",
            "-d",
            domains,
            "--email",
            email,
            "--agree-tos",
            "--logs-dir",
            "/var/tmp/bunkerweb",
            "--work-dir",
            "/var/lib/bunkerweb",
        ]
        + (["--staging"] if getenv("USE_LETS_ENCRYPT_STAGING", "no") == "yes" else []),
        stdin=DEVNULL,
        stderr=STDOUT,
        env=environ,
    )
    return proc.returncode


try:
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

            if exists(f"/etc/letsencrypt/live/{first_server}/cert.pem"):
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
                status = 1
                logger.error(
                    f"Certificate generation failed for domain(s) {domains} ...",
                )
            else:
                logger.info(
                    f"Certificate generation succeeded for domain(s) : {domains}"
                )

                if exists(f"/etc/letsencrypt/live/{first_server}/cert.pem"):
                    with open(f"/etc/letsencrypt/live/{first_server}/cert.pem") as f:
                        cert = f.read()

                    # Update db
                    err = db.update_job_cache(
                        "letsencrypt",
                        first_server,
                        "cert.pem",
                        cert,
                    )
                    if err:
                        logger.warning(f"Couldn't update db cache: {err}")

    # Singlesite case
    elif getenv("AUTO_LETS_ENCRYPT", "no") == "yes" and getenv("SERVER_NAME", ""):
        first_server = getenv("SERVER_NAME", "").split(" ")[0]
        domains = getenv("SERVER_NAME", "").replace(" ", ",")

        if exists(f"/etc/letsencrypt/live/{first_server}/cert.pem"):
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
                logger.info(
                    f"Certificate generation succeeded for domain(s) : {domains}"
                )

                if exists(f"/etc/letsencrypt/live/{first_server}/cert.pem"):
                    with open(f"/etc/letsencrypt/live/{first_server}/cert.pem") as f:
                        cert = f.read()

                    # Update db
                    err = db.update_job_cache(
                        "letsencrypt",
                        first_server,
                        "cert.pem",
                        cert,
                    )
                    if err:
                        logger.warning(f"Couldn't update db cache: {err}")
except:
    status = 1
    logger.error(f"Exception while running certbot-new.py :\n{format_exc()}")

sys_exit(status)
