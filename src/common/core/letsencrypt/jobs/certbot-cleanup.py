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

LOGGER = getLogger("LETS-ENCRYPT.CLEANUP")
status = 0

try:
    # Get env vars
    token = getenv("CERTBOT_TOKEN", "")
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
    instances = db.get_instances()

    LOGGER.info(f"Cleaning challenge from {len(instances)} instances")
    for instance in instances:
        api = API.from_instance(instance)
        sent, err, status, resp = api.request("DELETE", "/lets-encrypt/challenge", data={"token": token})
        if not sent:
            status = 1
            LOGGER.error(f"Can't send API request to {api.endpoint}/lets-encrypt/challenge : {err}")
        elif status != 200:
            status = 1
            LOGGER.error(f"Error while sending API request to {api.endpoint}/lets-encrypt/challenge : status = {resp['status']}, msg = {resp['msg']}")
        else:
            LOGGER.info(f"Successfully sent API request to {api.endpoint}/lets-encrypt/challenge")
except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-cleanup.py :\n{e}")

sys_exit(status)
