#!/usr/bin/python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
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

logger = setup_logger("Lets-encrypt.deploy", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Get env vars
    bw_integration = "Linux"
    integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
    os_release_path = Path(sep, "etc", "os-release")
    if getenv("KUBERNETES_MODE", "no") == "yes":
        bw_integration = "Kubernetes"
    elif getenv("SWARM_MODE", "no") == "yes":
        bw_integration = "Swarm"
    elif getenv("AUTOCONF_MODE", "no") == "yes":
        bw_integration = "Autoconf"
    elif integration_path.is_file():
        bw_integration = integration_path.read_text(encoding="utf-8").strip()
    elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
        bw_integration = "Docker"

    token = getenv("CERTBOT_TOKEN", "")

    logger.info(f"Certificates renewal for {getenv('RENEWED_DOMAINS')} successful")

    # Cluster case
    if bw_integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        # Create tarball of /var/cache/bunkerweb/letsencrypt
        tgz = BytesIO()

        with tar_open(mode="w:gz", fileobj=tgz, compresslevel=3) as tf:
            tf.add(
                join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc"),
                arcname="etc",
            )
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}

        db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)
        lock = Lock()

        with lock:
            instances = db.get_instances()

        for instance in instances:
            endpoint = f"http://{instance['hostname']}:{instance['port']}"
            host = instance["server_name"]
            api = API(endpoint, host=host)

            sent, err, status, resp = api.request("POST", "/lets-encrypt/certificates", files=files)
            if not sent:
                status = 1
                logger.error(f"Can't send API request to {api.endpoint}/lets-encrypt/certificates : {err}")
            elif status != 200:
                status = 1
                logger.error(f"Error while sending API request to {api.endpoint}/lets-encrypt/certificates : status = {resp['status']}, msg = {resp['msg']}")
            else:
                logger.info(
                    f"Successfully sent API request to {api.endpoint}/lets-encrypt/certificates",
                )
                sent, err, status, resp = api.request("POST", "/reload")
                if not sent:
                    status = 1
                    logger.error(f"Can't send API request to {api.endpoint}/reload : {err}")
                elif status != 200:
                    status = 1
                    logger.error(f"Error while sending API request to {api.endpoint}/reload : status = {resp['status']}, msg = {resp['msg']}")
                else:
                    logger.info(f"Successfully sent API request to {api.endpoint}/reload")
    # Linux case
    else:
        if (
            run(
                ["sudo", join(sep, "usr", "sbin", "nginx"), "-s", "reload"],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            ).returncode
            != 0
        ):
            status = 1
            logger.error("Error while reloading nginx")
        else:
            logger.info("Successfully reloaded nginx")
except:
    status = 1
    logger.error(f"Exception while running certbot-deploy.py :\n{format_exc()}")

sys_exit(status)
