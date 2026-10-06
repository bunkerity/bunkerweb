#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import getLogger  # type: ignore
from API import API  # type: ignore

LOGGER = getLogger("LETS-ENCRYPT.AUTH")
status = 0


def describe_api_error(http_status, resp) -> str:
    detail = f"status = {resp.get('status')}, msg = {resp.get('msg')}" if isinstance(resp, dict) else f"body = {str(resp)[:200]!r}"
    return f"HTTP {http_status}, {detail}"


try:
    # Get env vars
    token = getenv("CERTBOT_TOKEN", "")
    validation = getenv("CERTBOT_VALIDATION", "")
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

    instances = db.get_instances()

    LOGGER.info(f"Sending challenge to {len(instances)} instances")
    for instance in instances:
        api = API.from_instance(instance)
        sent, err, http_status, resp = api.request("POST", "/lets-encrypt/challenge", data={"token": token, "validation": validation})
        if not sent:
            status = 1
            LOGGER.error(f"Can't send API request to {api.endpoint}/lets-encrypt/challenge : {err}")
        elif http_status != 200:
            status = 1
            LOGGER.error(f"Error while sending API request to {api.endpoint}/lets-encrypt/challenge : {describe_api_error(http_status, resp)}")
        else:
            LOGGER.info(f"Successfully sent API request to {api.endpoint}/lets-encrypt/challenge")
except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-auth.py :\n{e}")

sys_exit(status)
