#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
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

from bunkernet import data
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore
from common_utils import bytes_hash  # type: ignore

LOGGER = setup_logger("BUNKERNET.data")
exit_status = 0


def check_bunkernet_activation():
    # Check if BunkerNet is activated for at least one server.
    # Returns: True if BunkerNet is activated, False otherwise
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug("Checking BunkerNet activation status")
    
    bunkernet_activated = False
    
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        server_names = getenv("SERVER_NAME", "www.example.com").split(" ")
        if getenv("LOG_LEVEL") == "debug":
            LOGGER.debug(f"Multisite mode - checking servers: {server_names}")
        
        for first_server in server_names:
            use_bunkernet = getenv(f"{first_server}_USE_BUNKERNET", "yes")
            if getenv("LOG_LEVEL") == "debug":
                LOGGER.debug(
                    f"Server {first_server}: USE_BUNKERNET={use_bunkernet}"
                )
            
            if use_bunkernet == "yes":
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True
        if getenv("LOG_LEVEL") == "debug":
            LOGGER.debug("Singlesite mode - BunkerNet activated")

    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug(f"BunkerNet activation result: {bunkernet_activated}")
    
    return bunkernet_activated


def setup_bunkernet_directories():
    # Create BunkerNet cache directories if they don't exist.
    # Returns: BunkerNet cache directory path
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)
    
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug(f"BunkerNet cache directory: {bunkernet_path}")
    
    return bunkernet_path


def get_instance_id_from_cache(job, bunkernet_path):
    # Get and cache BunkerNet instance ID.
    # Args: job (Job instance), bunkernet_path (Path to cache directory)
    # Returns: True if ID is available, False otherwise
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug("Getting instance ID from cache")
    
    # Get ID from cache
    bunkernet_id = job.get_cache("instance.id")
    if bunkernet_id:
        bunkernet_path.joinpath("instance.id").write_bytes(bunkernet_id)
        LOGGER.info("Successfully retrieved BunkerNet ID from db cache")
        
        if getenv("LOG_LEVEL") == "debug":
            LOGGER.debug(f"Instance ID: {bunkernet_id.decode()}")
    else:
        LOGGER.info("No BunkerNet ID found in db cache")

    # Check if ID is present
    id_file_exists = bunkernet_path.joinpath("instance.id").is_file()
    
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug(f"Instance ID file exists: {id_file_exists}")
    
    return id_file_exists


def check_cache_freshness(job):
    # Check if cached IP list is still fresh.
    # Args: job (Job instance for database operations)
    # Returns: True if cache is fresh, False if needs update
    is_cached = job.is_cached_file("ip.list", "day")
    
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug(f"IP list cache is fresh: {is_cached}")
    
    return is_cached


def download_threat_data():
    # Download threat intelligence data from BunkerNet API.
    # Returns: tuple (success, status_code, data)
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug("Downloading threat data from BunkerNet API")
    
    LOGGER.info("Downloading BunkerNet data ...")
    ok, status, response_data = data()
    
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug(f"Download response: ok={ok}, status={status}")
    
    return ok, status, response_data


def validate_api_response(status, response_data):
    # Validate the API response from BunkerNet.
    # Args: status (HTTP status code), response_data (Response data from API)
    # Returns: tuple (is_valid, exit_code)
    if status == 429:
        LOGGER.warning(
            "BunkerNet API is rate limiting us, trying again later..."
        )
        return False, 0
    elif status == 403:
        LOGGER.warning(
            "BunkerNet has banned this instance, retrying to download "
            "data later..."
        )
        return False, 0

    try:
        assert isinstance(response_data, dict)
    except AssertionError:
        LOGGER.error(
            f"Received invalid data from BunkerNet API while sending db "
            f"request : {response_data}"
        )
        return False, 2

    if response_data["result"] != "ok":
        LOGGER.error(
            f"Received error from BunkerNet API while sending db request : "
            f"{response_data['data']}, removing instance ID"
        )
        return False, 2
    
    if getenv("LOG_LEVEL") == "debug":
        data_count = len(response_data.get("data", []))
        LOGGER.debug(f"Received {data_count} threat entries")
    
    return True, 0


def save_threat_data(job, response_data):
    # Save downloaded threat data to cache.
    # Args: job (Job instance), response_data (Response data with threats)
    # Returns: int exit status (0=success, 1=reload needed, 2=error)
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug("Saving threat data to cache")
    
    LOGGER.info("Saving BunkerNet data ...")
    content = "\n".join(response_data["data"]).encode("utf-8")

    # Check if file has changed
    new_hash = bytes_hash(content)
    old_hash = job.cache_hash("ip.list")
    
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug(f"New hash: {new_hash}")
        LOGGER.debug(f"Old hash: {old_hash}")
    
    if new_hash == old_hash:
        LOGGER.info(
            "New file is identical to cache file, reload is not needed"
        )
        return 0

    # Put file in cache
    cached, err = job.cache_file("ip.list", content, checksum=new_hash)
    if not cached:
        LOGGER.error(f"Error while caching BunkerNet data : {err}")
        return 2

    LOGGER.info("Successfully saved BunkerNet data")
    
    if getenv("LOG_LEVEL") == "debug":
        threat_count = len(response_data["data"])
        LOGGER.debug(f"Cached {threat_count} threat entries")
    
    return 1


try:
    if not check_bunkernet_activation():
        LOGGER.info("BunkerNet is not activated, skipping download...")
        sys_exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = setup_bunkernet_directories()

    JOB = Job(LOGGER, __file__)

    # Create empty file in case it doesn't exist
    ip_list_path = bunkernet_path.joinpath("ip.list")

    # Get and cache instance ID
    if not get_instance_id_from_cache(JOB, bunkernet_path):
        LOGGER.warning(
            "Not downloading BunkerNet data because instance is not registered"
        )
        sys_exit(2)

    # Don't go further if the cache is fresh
    if check_cache_freshness(JOB):
        LOGGER.info("BunkerNet list is already in cache, skipping download...")
        sys_exit(0)

    exit_status = 1

    # Download data
    ok, status, response_data = download_threat_data()
    if not ok:
        LOGGER.error(
            f"Error while sending data request to BunkerNet API : "
            f"{response_data}"
        )
        sys_exit(2)

    # Validate API response
    is_valid, error_code = validate_api_response(status, response_data)
    if not is_valid:
        sys_exit(error_code)

    LOGGER.info("Successfully downloaded data from BunkerNet API")

    # Save data to cache
    save_status = save_threat_data(JOB, response_data)
    exit_status = save_status

except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    if getenv("LOG_LEVEL") == "debug":
        LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running bunkernet-data.py :\n{e}")

sys_exit(exit_status)