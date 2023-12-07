#!/usr/bin/python3
# -*- coding: utf-8 -*-

from os import _exit, getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",), ("core_plugins", "bunkernet", "jobs"))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import data
from API import API  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import bytes_hash, Job  # type: ignore

LOGGER = setup_logger("BUNKERNET", getenv("LOG_LEVEL", "INFO"))
JOB = Job(API(getenv("API_ADDR", ""), "job-bunkernet-data"), getenv("CORE_TOKEN", None))
exit_status = 0

try:
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE", "yes") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if getenv(f"{first_server}_USE_BUNKERNET", getenv("USE_BUNKERNET", "yes")) == "yes":
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True

    if not bunkernet_activated:
        LOGGER.info("BunkerNet is not activated, skipping download...")
        _exit(0)

    # Get ID from cache
    bunkernet_id = JOB.get_cache("instance.id")
    if bunkernet_id:
        LOGGER.info("Successfully retrieved BunkerNet ID from db cache")
    else:
        LOGGER.error("Not downloading BunkerNet data because instance is not registered")
        _exit(2)

    # Don't go further if the cache is fresh
    in_cache, is_cached = JOB.is_cached_file("ip.list", "day")
    if is_cached:
        LOGGER.info("BunkerNet list is already in cache, skipping download...")
        _exit(0)

    exit_status = 1

    # Download data
    LOGGER.info("Downloading BunkerNet data ...")
    ok, status, data = data(bunkernet_id.decode("utf-8"))
    if not ok:
        LOGGER.error(f"Error while sending data request to BunkerNet API : {data}")
        _exit(2)
    elif status == 429:
        LOGGER.warning("BunkerNet API is rate limiting us, trying again later...")
        _exit(0)
    elif status == 403:
        LOGGER.warning("BunkerNet has banned this instance, retrying a register later...")
        _exit(0)

    try:
        assert isinstance(data, dict)
    except AssertionError:
        LOGGER.error(f"Received invalid data from BunkerNet API while sending db request : {data}")
        _exit(2)

    if data["result"] != "ok":
        LOGGER.error(f"Received error from BunkerNet API while sending db request : {data['data']}, removing instance ID")
        _exit(2)

    LOGGER.info("Successfully downloaded data from BunkerNet API")

    # Writing data to file
    LOGGER.info("Saving BunkerNet data ...")
    content = "\n".join(data["data"]).encode("utf-8")

    new_hash = None
    if in_cache:
        # Check if file has changed
        new_hash = bytes_hash(content)
        old_hash = JOB.cache_hash("ip.list")
        if new_hash == old_hash:
            LOGGER.info("New file is identical to cache file, reload is not needed")
            _exit(0)

    # Put file in cache
    cached, err = JOB.cache_file("ip.list", content, checksum=new_hash)
    if not cached:
        LOGGER.error(f"Error while caching BunkerNet data : {err}")
        _exit(2)

    LOGGER.info("Successfully saved BunkerNet data")

    exit_status = 1
except:
    exit_status = 2
    LOGGER.error(f"Exception while running bunkernet-data.py :\n{format_exc()}")

sys_exit(exit_status)
