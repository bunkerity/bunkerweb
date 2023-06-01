#!/usr/bin/python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("api",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from API import API  # type: ignore

logger = setup_logger("Lets-encrypt.cleanup", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Get env vars
    bw_integration = "Linux"
    integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
    if getenv("KUBERNETES_MODE") == "yes":
        bw_integration = "Kubernetes"
    elif getenv("SWARM_MODE") == "yes":
        bw_integration = "Swarm"
    elif getenv("AUTOCONF_MODE") == "yes":
        bw_integration = "Autoconf"
    elif integration_path.is_file():
        integration = integration_path.read_text().strip()
    token = getenv("CERTBOT_TOKEN", "")

    # Cluster case
    if bw_integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        db = Database(
            logger,
            sqlalchemy_string=getenv("DATABASE_URI", None),
        )
        lock = Lock()
        with lock:
            instances = db.get_instances()

        for instance in instances:
            api = API(
                f"http://{instance['hostname']}:{instance['port']}",
                host=instance["server_name"],
            )
            sent, err, status, resp = api.request(
                "DELETE", "/lets-encrypt/challenge", data={"token": token}
            )
            if not sent:
                status = 1
                logger.error(
                    f"Can't send API request to {api.endpoint}/lets-encrypt/challenge : {err}"
                )
            elif status != 200:
                status = 1
                logger.error(
                    f"Error while sending API request to {api.endpoint}/lets-encrypt/challenge : status = {resp['status']}, msg = {resp['msg']}",
                )
            else:
                logger.info(
                    f"Successfully sent API request to {api.endpoint}/lets-encrypt/challenge",
                )
    # Linux case
    else:
        challenge_path = Path(
            sep,
            "var",
            "tmp",
            "bunkerweb",
            "lets-encrypt",
            ".well-known",
            "acme-challenge",
            token,
        )
        challenge_path.unlink(missing_ok=True)
except:
    status = 1
    logger.error(f"Exception while running certbot-cleanup.py :\n{format_exc()}")

sys_exit(status)
