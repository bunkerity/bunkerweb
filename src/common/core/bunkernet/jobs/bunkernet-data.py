#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import data
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore
from common_utils import bytes_hash  # type: ignore

LOGGER = getLogger("BUNKERNET.DATA")
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
        LOGGER.info("BunkerNet is not activated, skipping download...")
        sys_exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)

    JOB = Job(LOGGER, __file__)

    # Create empty file in case it doesn't exist
    ip_list_path = bunkernet_path.joinpath("ip.list")

    # Get ID from cache
    bunkernet_id = None
    bunkernet_id = JOB.get_cache("instance.id")
    if bunkernet_id:
        bunkernet_path.joinpath("instance.id").write_bytes(bunkernet_id)
        LOGGER.info("Successfully retrieved BunkerNet ID from db cache")
    else:
        LOGGER.info("No BunkerNet ID found in db cache")

    # Check if ID is present
    if not bunkernet_path.joinpath("instance.id").is_file():
        LOGGER.warning("Not downloading BunkerNet data because instance is not registered")
        sys_exit(2)

    # Don't go further if the cache is fresh
    if JOB.is_cached_file("ip.list", "day"):
        LOGGER.info("BunkerNet list is already in cache, skipping download...")
        sys_exit(0)

    exit_status = 1

    # Download data
    LOGGER.info("Downloading BunkerNet data ...")
    ok, status, data = data()
    if not ok:
        LOGGER.error(f"Error while sending data request to BunkerNet API : {data}")
        sys_exit(2)
    elif status == 429:
        LOGGER.warning("BunkerNet API is rate limiting us, trying again later...")
        sys_exit(0)
    elif status == 403:
        LOGGER.warning("BunkerNet has banned this instance, retrying to download data later...")
        sys_exit(0)

    try:
        assert isinstance(data, dict)
    except AssertionError:
        LOGGER.error(f"Received invalid data from BunkerNet API while sending db request : {data}")
        sys_exit(2)

    if data["result"] != "ok":
        LOGGER.error(f"Received error from BunkerNet API while sending db request : {data['data']}, removing instance ID")
        sys_exit(2)

    LOGGER.info("Successfully downloaded data from BunkerNet API")

    # Writing data to file
    LOGGER.info("Saving BunkerNet data ...")
    content = "\n".join(data["data"]).encode("utf-8")

    # Check if file has changed
    new_hash = bytes_hash(content)
    old_hash = JOB.cache_hash("ip.list")
    if new_hash == old_hash:
        LOGGER.info("New file is identical to cache file, reload is not needed")
        sys_exit(0)

    # Put file in cache
    cached, err = JOB.cache_file("ip.list", content, checksum=new_hash)
    if not cached:
        LOGGER.error(f"Error while caching BunkerNet data : {err}")
        sys_exit(2)

    LOGGER.info("Successfully saved BunkerNet data")

    exit_status = 1
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running bunkernet-data.py :\n{e}")

sys_exit(exit_status)
