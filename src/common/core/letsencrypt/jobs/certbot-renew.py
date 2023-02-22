#!/usr/bin/python3

from os import environ, getenv
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
    )
)

from logger import setup_logger


def renew(domain):
    environ["PYTHONPATH"] = "/usr/share/bunkerweb/deps/python"
    proc = run(
        [
            "/usr/share/bunkerweb/deps/python/bin/certbot",
            "renew",
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


logger = setup_logger("LETS-ENCRYPT", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
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
                or not Path(f"/etc/letsencrypt/live/{first_server}/cert.pem").exists()
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
        if Path(f"/etc/letsencrypt/live/{first_server}/cert.pem").exists():
            ret = renew(first_server)
            if ret != 0:
                status = 2
                logger.error(
                    f"Certificates renewal for {first_server} failed",
                )

except:
    status = 2
    logger.error(f"Exception while running certbot-renew.py :\n{format_exc()}")

sys_exit(status)
