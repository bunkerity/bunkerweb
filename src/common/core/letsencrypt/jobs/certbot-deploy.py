#!/usr/bin/python3

from io import BytesIO
from os import getenv
from os.path import exists
from subprocess import run, DEVNULL, STDOUT
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from traceback import format_exc

sys_path.append("/usr/share/bunkerweb/deps/python")
sys_path.append("/usr/share/bunkerweb/utils")
sys_path.append("/usr/share/bunkerweb/api")
sys_path.append("/usr/share/bunkerweb/db")

from Database import Database
from logger import setup_logger
from API import API

logger = setup_logger("Lets-encrypt", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
status = 0

try:
    # Get env vars
    bw_integration = None
    if getenv("KUBERNETES_MODE") == "yes":
        bw_integration = "Swarm"
    elif getenv("SWARM_MODE") == "yes":
        bw_integration = "Kubernetes"
    elif getenv("AUTOCONF_MODE") == "yes":
        bw_integration = "Autoconf"
    elif exists("/usr/share/bunkerweb/INTEGRATION"):
        with open("/usr/share/bunkerweb/INTEGRATION", "r") as f:
            bw_integration = f.read().strip()
    token = getenv("CERTBOT_TOKEN")

    logger.info(f"Certificates renewal for {getenv('RENEWED_DOMAINS')} successful")

    # Cluster case
    if bw_integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        # Create tarball of /data/cache/letsencrypt
        tgz = BytesIO()
        with tar_open(mode="w:gz", fileobj=tgz) as tf:
            tf.add("/data/cache/letsencrypt", arcname=".")
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}

        for instance in db.get_instances():
            endpoint = f"http://{instance['hostname']}:{instance['port']}"
            host = instance["server_name"]
            api = API(endpoint, host=host)
            sent, err, status, resp = api.request(
                "POST", "/lets-encrypt/certificates", files=files
            )
            if not sent:
                status = 1
                logger.error(
                    f"Can't send API request to {api.get_endpoint()}/lets-encrypt/certificates : {err}"
                )
            else:
                if status != 200:
                    status = 1
                    logger.error(
                        f"Error while sending API request to {api.get_endpoint()}/lets-encrypt/certificates : status = {resp['status']}, msg = {resp['msg']}"
                    )
                else:
                    logger.info(
                        f"Successfully sent API request to {api.get_endpoint()}/lets-encrypt/certificates",
                    )
                    sent, err, status, resp = api.request("POST", "/reload")
                    if not sent:
                        status = 1
                        logger.error(
                            f"Can't send API request to {api.get_endpoint()}/reload : {err}"
                        )
                    else:
                        if status != 200:
                            status = 1
                            logger.error(
                                f"Error while sending API request to {api.get_endpoint()}/reload : status = {resp['status']}, msg = {resp['msg']}"
                            )
                        else:
                            logger.info(
                                f"Successfully sent API request to {api.get_endpoint()}/reload"
                            )
    # Linux case
    else:
        proc = run(
            ["nginx", "-s", "reload"],
            stdin=DEVNULL,
            stderr=STDOUT,
        )
        if proc.returncode != 0:
            status = 1
            logger.error("Error while reloading nginx")
        else:
            logger.info("Successfully reloaded nginx")

except:
    status = 1
    logger.error(f"Exception while running certbot-deploy.py :\n{format_exc()}")

sys_exit(status)
