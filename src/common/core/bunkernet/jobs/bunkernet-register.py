#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="bunkernet-register",
    log_file_path="/var/log/bunkerweb/bunkernet.log"
)

logger.debug("Debug mode enabled for bunkernet")

from bunkernet import register
from jobs import Job  # type: ignore

exit_status = 0

try:
    logger.debug("Starting bunkernet registration process")
    
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    logger.debug("Checking bunkernet activation status")
    
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        logger.debug("Processing multisite configuration")
        servers = getenv("SERVER_NAME", "www.example.com").split(" ")
        logger.debug(f"Checking {len(servers)} servers for bunkernet activation")
        
        for first_server in servers:
            if getenv(f"{first_server}_USE_BUNKERNET", "yes") == "yes":
                bunkernet_activated = True
                logger.debug(f"Bunkernet activated for server: {first_server}")
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        logger.debug("Bunkernet activated for singlesite")
        bunkernet_activated = True

    if not bunkernet_activated:
        logger.info("BunkerNet is not activated, skipping registration...")
        sys_exit(0)

    # Get ID from cache
    logger.debug("Creating Job instance and checking for existing ID")
    JOB = Job(logger, __file__)
    bunkernet_id = JOB.get_cache("instance.id")
    logger.debug(f"Cached bunkernet ID: {bunkernet_id is not None}")

    # Register instance
    registered = False
    if not bunkernet_id:
        logger.info("No BunkerNet ID found in db cache, Registering instance on BunkerNet API ...")
        logger.debug("Calling bunkernet register API")
        
        ok, status, data = register()
        logger.debug(f"Register response: ok={ok}, status={status}")
        
        if not ok:
            logger.error(f"Error while sending register request to BunkerNet API : {data}")
            sys_exit(2)
        elif status == 429:
            logger.warning("BunkerNet API is rate limiting us, trying again later...")
            sys_exit(0)
        elif status == 403:
            logger.warning("BunkerNet has banned this instance, retrying a register later...")
            sys_exit(0)

        try:
            assert isinstance(data, dict)
            logger.debug(f"Register response data keys: {list(data.keys())}")
        except AssertionError:
            logger.error(f"Received invalid data from BunkerNet API while sending db request : {data}, retrying later...")
            sys_exit(2)

        bunkernet_id = data.get("data")
        logger.debug(f"Extracted bunkernet ID: {bunkernet_id}")
        
        if status != 200:
            logger.error(f"Error {status} from BunkerNet API : {bunkernet_id}")
            sys_exit(2)
        elif data.get("result", "ko") != "ok":
            logger.error(f"Received error from BunkerNet API while sending register request : {bunkernet_id}")
            sys_exit(2)

        assert isinstance(bunkernet_id, str), f"Received invalid bunkernet id : {bunkernet_id}"

        registered = True
        exit_status = 1
        logger.info(f"Successfully registered on BunkerNet API with instance id {data['data']}")
        logger.debug(f"Registration successful, ID length: {len(bunkernet_id)}")
    else:
        bunkernet_id = bunkernet_id.decode()
        logger.info(f"Already registered on BunkerNet API with instance id {bunkernet_id}")
        logger.debug("Using existing cached bunkernet ID")

    # Update cache with new bunkernet ID
    if registered:
        logger.debug("Caching new bunkernet ID to database")
        cached, err = JOB.cache_file("instance.id", bunkernet_id.encode())
        if not cached:
            logger.error(f"Error while saving BunkerNet data to db cache : {err}")
        else:
            logger.info("Successfully saved BunkerNet data to db cache")
            logger.debug("Bunkernet ID successfully cached")
    
    logger.debug("Bunkernet registration process completed")
    
except SystemExit as e:
    exit_status = e.code
    logger.debug(f"SystemExit with code: {exit_status}")
except BaseException as e:
    exit_status = 2
    logger.exception("Exception while running bunkernet-register.py")

logger.debug(f"Exiting with status: {exit_status}")
sys_exit(exit_status)
