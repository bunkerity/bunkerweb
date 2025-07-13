#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
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
    title="bunkernet-data",
    log_file_path="/var/log/bunkerweb/bunkernet.log"
)

logger.debug("Debug mode enabled for bunkernet")

from bunkernet import data
from jobs import Job  # type: ignore
from common_utils import bytes_hash  # type: ignore

exit_status = 0

try:
    logger.debug("Starting bunkernet data download process")
    
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
        logger.info("BunkerNet is not activated, skipping download...")
        sys_exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Bunkernet cache directory: {bunkernet_path}")

    logger.debug("Creating Job instance")
    JOB = Job(logger, __file__)

    # Create empty file in case it doesn't exist
    ip_list_path = bunkernet_path.joinpath("ip.list")
    logger.debug(f"IP list path: {ip_list_path}")

    # Get ID from cache
    bunkernet_id = None
    logger.debug("Retrieving bunkernet ID from cache")
    bunkernet_id = JOB.get_cache("instance.id")
    if bunkernet_id:
        bunkernet_path.joinpath("instance.id").write_bytes(bunkernet_id)
        logger.info("Successfully retrieved BunkerNet ID from db cache")
        logger.debug(f"Bunkernet ID length: {len(bunkernet_id)} bytes")
    else:
        logger.info("No BunkerNet ID found in db cache")

    # Check if ID is present
    id_file = bunkernet_path.joinpath("instance.id")
    if not id_file.is_file():
        logger.warning("Not downloading BunkerNet data because instance is not registered")
        sys_exit(2)

    # Don't go further if the cache is fresh
    logger.debug("Checking if IP list cache is fresh")
    if JOB.is_cached_file("ip.list", "day"):
        logger.info("BunkerNet list is already in cache, skipping download...")
        sys_exit(0)

    exit_status = 1
    logger.debug("Cache is stale, proceeding with download")

    # Download data
    logger.info("Downloading BunkerNet data ...")
    logger.debug("Calling bunkernet data API")
    
    ok, status, data_response = data()
    logger.debug(f"Data response: ok={ok}, status={status}")
    
    if not ok:
        logger.error(f"Error while sending data request to BunkerNet API : {data_response}")
        sys_exit(2)
    elif status == 429:
        logger.warning("BunkerNet API is rate limiting us, trying again later...")
        sys_exit(0)
    elif status == 403:
        logger.warning("BunkerNet has banned this instance, retrying to download data later...")
        sys_exit(0)

    try:
        assert isinstance(data_response, dict)
        logger.debug(f"Data response keys: {list(data_response.keys())}")
    except AssertionError:
        logger.error(f"Received invalid data from BunkerNet API while sending db request : {data_response}")
        sys_exit(2)

    if data_response["result"] != "ok":
        logger.error(f"Received error from BunkerNet API while sending db request : {data_response['data']}, removing instance ID")
        sys_exit(2)

    logger.info("Successfully downloaded data from BunkerNet API")
    logger.debug(f"Received {len(data_response['data'])} IP entries")

    # Writing data to file
    logger.info("Saving BunkerNet data ...")
    content = "\n".join(data_response["data"]).encode("utf-8")
    logger.debug(f"Generated content size: {len(content)} bytes")

    # Check if file has changed
    logger.debug("Checking if content has changed")
    new_hash = bytes_hash(content)
    old_hash = JOB.cache_hash("ip.list")
    logger.debug(f"New hash: {new_hash}, Old hash: {old_hash}")
    
    if new_hash == old_hash:
        logger.info("New file is identical to cache file, reload is not needed")
        sys_exit(0)

    # Put file in cache
    logger.debug("Caching new IP list data")
    cached, err = JOB.cache_file("ip.list", content, checksum=new_hash)
    if not cached:
        logger.error(f"Error while caching BunkerNet data : {err}")
        sys_exit(2)

    logger.info("Successfully saved BunkerNet data")
    logger.debug("IP list successfully cached with new hash")

    exit_status = 1
    logger.debug("Bunkernet data download process completed successfully")
    
except SystemExit as e:
    exit_status = e.code
    logger.debug(f"SystemExit with code: {exit_status}")
except BaseException as e:
    exit_status = 2
    logger.exception("Exception while running bunkernet-data.py")

logger.debug(f"Exiting with status: {exit_status}")
sys_exit(exit_status)
