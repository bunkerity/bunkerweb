#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from API import API  # type: ignore

LOGGER = setup_logger("Lets-encrypt.deploy", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Get env vars
    token = getenv("CERTBOT_TOKEN", "")

    LOGGER.info(f"Certificates renewal for {getenv('RENEWED_DOMAINS')} successful")

    # Create tarball of /var/cache/bunkerweb/letsencrypt
    tgz = BytesIO()

    with tar_open(mode="w:gz", fileobj=tgz, compresslevel=3) as tf:
        tf.add(join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc"), arcname="etc")
    tgz.seek(0, 0)
    files = {"archive.tar.gz": tgz}

    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI", None))

    instances = db.get_instances()
    services = db.get_non_default_settings(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME"))["SERVER_NAME"].split(" ")

    reload_min_timeout = getenv("RELOAD_MIN_TIMEOUT", "5")

    if not reload_min_timeout.isdigit():
        LOGGER.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
        reload_min_timeout = 5

    reload_min_timeout = int(reload_min_timeout)

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
            sent, err, status, resp = api.request("POST", "/reload", timeout=max(reload_min_timeout, 2 * len(services)))
            if not sent:
                status = 1
                LOGGER.error(f"Can't send API request to {api.endpoint}/reload : {err}")
            elif status != 200:
                status = 1
                LOGGER.error(f"Error while sending API request to {api.endpoint}/reload : status = {resp['status']}, msg = {resp['msg']}")
            else:
                LOGGER.info(f"Successfully sent API request to {api.endpoint}/reload")
except:
    status = 1
    LOGGER.error(f"Exception while running certbot-deploy.py :\n{format_exc()}")

sys_exit(status)
