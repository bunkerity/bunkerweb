#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths) 
    for paths in (
        ("deps", "python"), 
        ("utils",), 
        ("db",)
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import register
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("BUNKERNET.register")
exit_status = 0


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def check_bunkernet_activation():
    # Check if BunkerNet is activated for at least one server.
    # Returns: True if BunkerNet is activated, False otherwise
    debug_log(LOGGER, "Checking BunkerNet activation status")
    
    bunkernet_activated = False
    
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        server_names = getenv("SERVER_NAME", "www.example.com").split(" ")
        debug_log(LOGGER, f"Multisite mode - checking servers: {server_names}")
        
        for first_server in server_names:
            use_bunkernet = getenv(f"{first_server}_USE_BUNKERNET", "yes")
            debug_log(LOGGER,
                f"Server {first_server}: USE_BUNKERNET={use_bunkernet}")
            
            if use_bunkernet == "yes":
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True
        debug_log(LOGGER, "Singlesite mode - BunkerNet activated")

    debug_log(LOGGER, f"BunkerNet activation result: {bunkernet_activated}")
    
    return bunkernet_activated


def get_cached_id(job):
    # Get BunkerNet instance ID from cache.
    # Args: job (Job instance for database operations)
    # Returns: bytes or None (cached instance ID or None if not found)
    debug_log(LOGGER, "Getting BunkerNet ID from cache")
    
    bunkernet_id = job.get_cache("instance.id")
    
    if bunkernet_id:
        debug_log(LOGGER, f"Found cached ID: {bunkernet_id.decode()}")
    else:
        debug_log(LOGGER, "No cached ID found")
    
    return bunkernet_id


def register_instance():
    # Register this instance with BunkerNet API.
    # Returns: tuple (bunkernet_id, registered_flag, exit_status)
    debug_log(LOGGER, "Registering instance with BunkerNet API")
    
    LOGGER.info(
        "No BunkerNet ID found in db cache, Registering instance on "
        "BunkerNet API ..."
    )
    
    ok, status, data = register()
    
    debug_log(LOGGER, f"Registration response: ok={ok}, status={status}")
    
    if not ok:
        LOGGER.error(
            f"Error while sending register request to BunkerNet API : {data}"
        )
        return None, False, 2
    elif status == 429:
        LOGGER.warning(
            "BunkerNet API is rate limiting us, trying again later..."
        )
        return None, False, 0
    elif status == 403:
        LOGGER.warning(
            "BunkerNet has banned this instance, retrying a register later..."
        )
        return None, False, 0

    try:
        assert isinstance(data, dict)
    except AssertionError:
        LOGGER.error(
            f"Received invalid data from BunkerNet API while sending db "
            f"request : {data}, retrying later..."
        )
        return None, False, 2

    bunkernet_id = data.get("data")
    if status != 200:
        LOGGER.error(f"Error {status} from BunkerNet API : {bunkernet_id}")
        return None, False, 2
    elif data.get("result", "ko") != "ok":
        LOGGER.error(
            f"Received error from BunkerNet API while sending register "
            f"request : {bunkernet_id}"
        )
        return None, False, 2

    assert isinstance(bunkernet_id, str), (
        f"Received invalid bunkernet id : {bunkernet_id}"
    )

    debug_log(LOGGER, f"Successfully registered with ID: {bunkernet_id}")

    LOGGER.info(
        f"Successfully registered on BunkerNet API with instance id "
        f"{data['data']}"
    )
    
    return bunkernet_id, True, 1


def cache_instance_id(job, bunkernet_id):
    # Cache the BunkerNet instance ID.
    # Args: job (Job instance), bunkernet_id (Instance ID to cache)
    # Returns: int exit status (0 for success, 2 for error)
    debug_log(LOGGER, f"Caching instance ID: {bunkernet_id}")
    
    cached, err = job.cache_file("instance.id", bunkernet_id.encode())
    if not cached:
        LOGGER.error(f"Error while saving BunkerNet data to db cache : {err}")
        return 2
    else:
        LOGGER.info("Successfully saved BunkerNet data to db cache")
        return 0


try:
    if not check_bunkernet_activation():
        LOGGER.info("BunkerNet is not activated, skipping registration...")
        sys_exit(0)

    # Get ID from cache
    JOB = Job(LOGGER, __file__)
    bunkernet_id = get_cached_id(JOB)

    # Register instance if needed
    registered = False
    if not bunkernet_id:
        bunkernet_id, registered, status = register_instance()
        if bunkernet_id is None:
            sys_exit(status)
        exit_status = status
    else:
        bunkernet_id = bunkernet_id.decode()
        LOGGER.info(
            f"Already registered on BunkerNet API with instance id "
            f"{bunkernet_id}"
        )

    # Update cache with new bunkernet ID
    if registered:
        cache_status = cache_instance_id(JOB, bunkernet_id)
        if cache_status != 0:
            exit_status = cache_status

except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    debug_log(LOGGER, format_exc())
    LOGGER.error(f"Exception while running bunkernet-register.py :\n{e}")

sys_exit(exit_status)