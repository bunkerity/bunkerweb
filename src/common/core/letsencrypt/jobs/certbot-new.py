#!/usr/bin/python3

from os import environ, getenv
from os.path import exists
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/usr/share/bunkerweb/deps/python")
sys_path.append("/usr/share/bunkerweb/utils")

from logger import setup_logger


def certbot_new(domains, email):
    cmd = f"/usr/share/bunkerweb/deps/python/bin/certbot certonly --manual --preferred-challenges=http --manual-auth-hook /usr/share/bunkerweb/core/letsencrypt/jobs/certbot-auth.py --manual-cleanup-hook /usr/share/bunkerweb/core/letsencrypt/jobs/certbot-cleanup.py -n -d {domains} --email {email} --agree-tos"
    if getenv("USE_LETS_ENCRYPT_STAGING") == "yes":
        cmd += " --staging"
    environ["PYTHONPATH"] = "/usr/share/bunkerweb/deps/python"
    proc = run(
        cmd.split(" "),
        stdin=DEVNULL,
        stderr=STDOUT,
        env=environ,
    )
    return proc.returncode


logger = setup_logger("LETS-ENCRYPT", getenv("LOG_LEVEL", "INFO"))
status = 0

try:

    # Multisite case
    if getenv("MULTISITE") == "yes":
        for first_server in getenv("SERVER_NAME").split(" "):
            if (
                getenv(f"{first_server}_AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT"))
                != "yes"
            ):
                continue
            if first_server == "":
                continue
            real_server_name = getenv(f"{first_server}_SERVER_NAME", first_server)
            domains = real_server_name.replace(" ", ",")
            if exists(f"/etc/letsencrypt/live/{first_server}/cert.pem"):
                logger.info(
                    f"Certificates already exists for domain(s) {domains}",
                )
                continue
            real_email = getenv(
                f"{first_server}_EMAIL_LETS_ENCRYPT",
                getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}"),
            )
            if real_email == "":
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

    # Singlesite case
    elif getenv("AUTO_LETS_ENCRYPT") == "yes" and getenv("SERVER_NAME") != "":
        first_server = getenv("SERVER_NAME").split(" ")[0]
        domains = getenv("SERVER_NAME").replace(" ", ",")
        if exists(f"/etc/letsencrypt/live/{first_server}/cert.pem"):
            logger.info(f"Certificates already exists for domain(s) {domains}")
        else:
            real_email = getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}")
            if real_email == "":
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


except:
    status = 1
    logger.error(f"Exception while running certbot-new.py :\n{format_exc()}")

sys_exit(status)
