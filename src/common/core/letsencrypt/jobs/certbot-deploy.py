#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from threading import Lock
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from common_utils import get_integration  # type: ignore
from logger import setup_logger  # type: ignore
from API import API  # type: ignore

LOGGER = setup_logger("Lets-encrypt.deploy", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Get env vars
    token = getenv("CERTBOT_TOKEN", "")

    LOGGER.info(f"Certificates renewal for {getenv('RENEWED_DOMAINS')} successful")

    # Cluster case
    if get_integration() in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        # Create tarball of /var/cache/bunkerweb/letsencrypt
        tgz = BytesIO()

        with tar_open(mode="w:gz", fileobj=tgz, compresslevel=3) as tf:
            tf.add(join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc"), arcname="etc")
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}

        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI", None))
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
                LOGGER.error(f"Can't send API request to {api.endpoint}/lets-encrypt/certificates : {err}")
            elif status != 200:
                status = 1
                LOGGER.error(f"Error while sending API request to {api.endpoint}/lets-encrypt/certificates : status = {resp['status']}, msg = {resp['msg']}")
            else:
                LOGGER.info(
                    f"Successfully sent API request to {api.endpoint}/lets-encrypt/certificates",
                )
                sent, err, status, resp = api.request("POST", "/reload")
                if not sent:
                    status = 1
                    LOGGER.error(f"Can't send API request to {api.endpoint}/reload : {err}")
                elif status != 200:
                    status = 1
                    LOGGER.error(f"Error while sending API request to {api.endpoint}/reload : status = {resp['status']}, msg = {resp['msg']}")
                else:
                    LOGGER.info(f"Successfully sent API request to {api.endpoint}/reload")
    # Linux case
    else:
        if run([join(sep, "usr", "sbin", "nginx"), "-s", "reload"], stdin=DEVNULL, stderr=STDOUT, check=False).returncode != 0:
            status = 1
            LOGGER.error("Error while reloading nginx")
        else:
            LOGGER.info("Successfully reloaded nginx")
except:
    status = 1
    LOGGER.error(f"Exception while running certbot-deploy.py :\n{format_exc()}")

sys_exit(status)
