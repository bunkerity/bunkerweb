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

try:
    # Get env vars
    token = getenv("CERTBOT_TOKEN", "")
    validation = getenv("CERTBOT_VALIDATION", "")
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

    instances = db.get_instances()

    LOGGER.info(f"Sending challenge to {len(instances)} instances")
    LOGGER.debug(f"Challenge data - token length: {len(token)}, validation length: {len(validation)}")

    for instance in instances:
        api = API.from_instance(instance)
        # Pass dict directly so API.request() uses kwargs["json"] = data, which sets
        # Content-Type: application/json automatically via the requests library.
        # Passing bytes instead would use kwargs["data"] = data with no Content-Type,
        # causing the Lua handler's json.decode() to fail ("json body decoding failed").
        payload = {"token": token, "validation": validation}
        LOGGER.debug(f"Sending payload to {api.endpoint}: {payload}")
        sent, err, status, resp = api.request("POST", "/lets-encrypt/challenge", data=payload)
        if not sent:
            status = 1
            LOGGER.error(f"Can't send API request to {api.endpoint}/lets-encrypt/challenge : {err}")
        elif status != 200:
            status = 1
            # Log HTTP status directly from the return value rather than from resp dict,
            # since resp structure varies and may not always have 'status'/'msg' keys.
            LOGGER.error(f"Error while sending API request (HTTP {status}) to {api.endpoint}/lets-encrypt/challenge : {resp}")
            LOGGER.debug(f"Full response: {resp}")
        else:
            LOGGER.info(f"Successfully sent API request to {api.endpoint}/lets-encrypt/challenge")
except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-auth.py :\n{e}")

sys_exit(status)
