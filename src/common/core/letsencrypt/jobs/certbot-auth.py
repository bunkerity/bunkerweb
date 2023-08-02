#!/usr/bin/python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
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

LOGGER = setup_logger("Lets-encrypt.auth", getenv("LOG_LEVEL", "INFO"))
CORE_API = API(getenv("API_ADDR", ""), "job-certbot-auth")
API_TOKEN = getenv("API_TOKEN", None)
status = 0

try:
    token = getenv("CERTBOT_TOKEN", "")
    validation = getenv("CERTBOT_VALIDATION", "")

    sent, err, status, resp = CORE_API.request(
        "POST",
        "/lets-encrypt/challenge",
        data={"token": token, "validation": validation},
        additonal_headers={"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {},
    )
    if not sent:
        status = 1
        LOGGER.error(
            f"Can't send API request to {CORE_API.endpoint}/lets-encrypt/challenge : {err}"
        )
    elif status != 200:
        status = 1
        LOGGER.error(
            f"Error while sending API request to {CORE_API.endpoint}/lets-encrypt/challenge : status = {resp['status']}, msg = {resp['msg']}",
        )
    else:
        LOGGER.info(
            f"Successfully sent API request to {CORE_API.endpoint}/lets-encrypt/challenge",
        )
except:
    status = 1
    LOGGER.error(f"Exception while running certbot-auth.py :\n{format_exc()}")

sys_exit(status)
