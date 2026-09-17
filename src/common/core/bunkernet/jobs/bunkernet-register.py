#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from json import dumps, loads
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
        for first_server in getenv("SERVER_NAME", "www.example.com").split():
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

    def retry_later(code):
        try:
            retry = loads(JOB.get_cache("register.retry") or b"{}")
        except (TypeError, ValueError):
            retry = {}
        attempt = retry.get("attempt", 0) + 1
        deadline = datetime.now().astimezone() + timedelta(hours=min(2 ** (attempt - 1), 24))
        cached, err = JOB.cache_file("register.retry", dumps({"deadline": deadline.isoformat(), "attempt": attempt, "code": code}).encode())
        if not cached:
            LOGGER.error(f"Error while saving BunkerNet retry data to db cache : {err}")

    # Register instance
    registered = False
    if not bunkernet_id:
        retry = JOB.get_cache("register.retry")
        if retry:
            with suppress(KeyError, TypeError, ValueError):
                retry = loads(retry)
                deadline = datetime.fromisoformat(retry["deadline"])
                now = datetime.now().astimezone()
                if now < deadline <= now + timedelta(hours=24):
                    LOGGER.warning(
                        f"Retrying registration in {deadline - now}; delete register.retry in the scheduler BunkerNet job cache under /var/cache/bunkerweb/bunkernet/ to reset it (the UI cache delete does not remove the on-disk copy)"
                    )
                    sys_exit(retry.get("code", 0))

        LOGGER.info("No BunkerNet ID found in db cache, Registering instance on BunkerNet API ...")
        ok, status, data = register()
        LOGGER.debug(f"Register API reply - ok: {ok}, status: {status}, data: {data}")
        if not ok:
            LOGGER.error(f"Error while sending register request to BunkerNet API : {data}")
            retry_later(2)
            sys_exit(2)
        elif status == 429:
            LOGGER.warning("BunkerNet API is rate limiting us, trying again later...")
            retry_later(0)
            sys_exit(0)
        elif status == 403:
            LOGGER.warning("BunkerNet has banned this instance, retrying a register later...")
            retry_later(0)
            sys_exit(0)

        try:
            assert isinstance(data, dict)
        except AssertionError:
            LOGGER.error(f"Received invalid data from BunkerNet API while sending db request : {data}, retrying later...")
            retry_later(2)
            sys_exit(2)

        bunkernet_id = data.get("data")
        if status != 200:
            LOGGER.error(f"Error {status} from BunkerNet API : {bunkernet_id}")
            retry_later(2)
            sys_exit(2)
        elif data.get("result", "ko") != "ok":
            LOGGER.error(f"Received error from BunkerNet API while sending register request : {bunkernet_id}")
            retry_later(2)
            sys_exit(2)

        if not isinstance(bunkernet_id, str):
            retry_later(2)
        assert isinstance(bunkernet_id, str), f"Received invalid bunkernet id : {bunkernet_id}"

        registered = True
        exit_status = 1
        LOGGER.info(f"Successfully registered on BunkerNet API with instance id {data['data']}")
    else:
        bunkernet_id = bunkernet_id.decode()
        JOB.del_cache("register.retry")
        LOGGER.info(f"Already registered on BunkerNet API with instance id {bunkernet_id}")

    # Update cache with new bunkernet ID
    if registered:
        cached, err = JOB.cache_file("instance.id", bunkernet_id.encode())
        if not cached:
            LOGGER.error(f"Error while saving BunkerNet data to db cache : {err}")
        else:
            JOB.del_cache("register.retry")
            LOGGER.info("Successfully saved BunkerNet data to db cache")
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running bunkernet-register.py :\n{e}")

sys_exit(exit_status)
