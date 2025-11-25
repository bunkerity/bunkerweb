#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import register
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("BUNKERNET.REGISTER")
exit_status = 0

try:
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "www.example.com").split(" "):
            if getenv(f"{first_server}_USE_BUNKERNET", "yes") == "yes":
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True

    if not bunkernet_activated:
        LOGGER.info("BunkerNet is not activated, skipping registration...")
        sys_exit(0)

    # Get ID from cache
    JOB = Job(LOGGER, __file__)
    bunkernet_id = JOB.get_cache("instance.id")

    # Register instance
    registered = False
    if not bunkernet_id:
        LOGGER.info("No BunkerNet ID found in db cache, Registering instance on BunkerNet API ...")
        ok, status, data = register()
        if not ok:
            LOGGER.error(f"Error while sending register request to BunkerNet API : {data}")
            sys_exit(2)
        elif status == 429:
            LOGGER.warning("BunkerNet API is rate limiting us, trying again later...")
            sys_exit(0)
        elif status == 403:
            LOGGER.warning("BunkerNet has banned this instance, retrying a register later...")
            sys_exit(0)

        try:
            assert isinstance(data, dict)
        except AssertionError:
            LOGGER.error(f"Received invalid data from BunkerNet API while sending db request : {data}, retrying later...")
            sys_exit(2)

        bunkernet_id = data.get("data")
        if status != 200:
            LOGGER.error(f"Error {status} from BunkerNet API : {bunkernet_id}")
            sys_exit(2)
        elif data.get("result", "ko") != "ok":
            LOGGER.error(f"Received error from BunkerNet API while sending register request : {bunkernet_id}")
            sys_exit(2)

        assert isinstance(bunkernet_id, str), f"Received invalid bunkernet id : {bunkernet_id}"

        registered = True
        exit_status = 1
        LOGGER.info(f"Successfully registered on BunkerNet API with instance id {data['data']}")
    else:
        bunkernet_id = bunkernet_id.decode()
        LOGGER.info(f"Already registered on BunkerNet API with instance id {bunkernet_id}")

    # Update cache with new bunkernet ID
    if registered:
        cached, err = JOB.cache_file("instance.id", bunkernet_id.encode())
        if not cached:
            LOGGER.error(f"Error while saving BunkerNet data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved BunkerNet data to db cache")
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running bunkernet-register.py :\n{e}")

sys_exit(exit_status)
