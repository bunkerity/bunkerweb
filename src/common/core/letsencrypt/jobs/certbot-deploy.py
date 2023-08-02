#!/usr/bin/python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("api",),
        ("utils",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("Lets-encrypt.deploy", getenv("LOG_LEVEL", "INFO"))
CORE_API = API(getenv("API_ADDR", ""), "job-certbot-deploy")
API_TOKEN = getenv("API_TOKEN", None)
status = 0

try:
    token = getenv("CERTBOT_TOKEN", "")

    LOGGER.info(f"Certificates renewal for {getenv('RENEWED_DOMAINS', '')} successful")

    tgz = BytesIO()

    with tar_open(mode="w:gz", fileobj=tgz, compresslevel=3) as tf:
        tf.add(
            join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc"),
            arcname="etc",
        )
    tgz.seek(0, 0)
    files = {"certificates": tgz}

    sent, err, status, resp = CORE_API.request(
        "POST",
        "/lets-encrypt/certificates",
        files=files,
        additonal_headers={"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {},
    )
    if not sent:
        status = 1
        LOGGER.error(
            f"Can't send API request to {CORE_API.endpoint}/lets-encrypt/certificates : {err}"
        )
    elif status != 200:
        status = 1
        LOGGER.error(
            f"Error while sending API request to {CORE_API.endpoint}/lets-encrypt/certificates : status = {resp['status']}, msg = {resp['msg']}"
        )
    else:
        LOGGER.info(
            f"Successfully sent API request to {CORE_API.endpoint}/lets-encrypt/certificates",
        )

        sent, err, status, resp = CORE_API.request(
            "POST",
            "/reload",
            additonal_headers={"Authorization": f"Bearer {API_TOKEN}"}
            if API_TOKEN
            else {},
        )
        if not sent:
            status = 1
            LOGGER.error(
                f"Can't send API request to {CORE_API.endpoint}/reload : {err}"
            )
        elif status != 200:
            status = 1
            LOGGER.error(
                f"Error while sending API request to {CORE_API.endpoint}/reload : status = {resp['status']}, msg = {resp['msg']}"
            )
        else:
            LOGGER.info(f"Successfully sent API request to {CORE_API.endpoint}/reload")
except:
    status = 1
    LOGGER.error(f"Exception while running certbot-deploy.py :\n{format_exc()}")

sys_exit(status)
