#!/usr/bin/python3

from os import _exit, getenv, makedirs
from os.path import isfile
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/db")
sys_path.append("/opt/bunkerweb/core/bunkernet/jobs")

from bunkernet import data
from Database import Database
from logger import setup_logger
from jobs import cache_file, cache_hash, file_hash, is_cached_file

logger = setup_logger("BUNKERNET", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
status = 0

try:

    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE") == "yes":
        for first_server in getenv("SERVER_NAME").split(" "):
            if (
                getenv(f"{first_server}_USE_BUNKERNET", getenv("USE_BUNKERNET"))
                == "yes"
            ):
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET") == "yes":
        bunkernet_activated = True
    if not bunkernet_activated:
        logger.info("BunkerNet is not activated, skipping download...")
        _exit(0)

    # Create directory if it doesn't exist
    makedirs("/opt/bunkerweb/cache/bunkernet", exist_ok=True)

    # Check if ID is present
    if not isfile("/opt/bunkerweb/cache/bunkernet/instance.id"):
        logger.error(
            "Not downloading BunkerNet data because instance is not registered",
        )
        _exit(2)

    # Don't go further if the cache is fresh
    if is_cached_file("/opt/bunkerweb/cache/bunkernet/ip.list", "day"):
        logger.info(
            "BunkerNet list is already in cache, skipping download...",
        )
        _exit(0)

    # Download data
    logger.info("Downloading BunkerNet data ...")
    ok, status, data = data()
    if not ok:
        logger.error(
            f"Error while sending data request to BunkerNet API : {data}",
        )
        _exit(2)
    elif status == 429:
        logger.warning(
            "BunkerNet API is rate limiting us, trying again later...",
        )
        _exit(0)
    elif data["result"] != "ok":
        logger.error(
            f"Received error from BunkerNet API while sending db request : {data['data']}, removing instance ID",
        )
        _exit(2)
    logger.info("Successfully downloaded data from BunkerNet API")

    # Writing data to file
    logger.info("Saving BunkerNet data ...")
    with open("/opt/bunkerweb/tmp/bunkernet-ip.list", "w") as f:
        for ip in data["data"]:
            f.write(f"{ip}\n")

    # Check if file has changed
    new_hash = file_hash("/opt/bunkerweb/tmp/bunkernet-ip.list")
    old_hash = cache_hash("/opt/bunkerweb/cache/bunkernet/ip.list")
    if new_hash == old_hash:
        logger.info(
            "New file is identical to cache file, reload is not needed",
        )
        _exit(0)

    # Put file in cache
    cached, err = cache_file(
        "/opt/bunkerweb/tmp/bunkernet-ip.list",
        "/opt/bunkerweb/cache/bunkernet/ip.list",
        new_hash,
    )
    if not cached:
        logger.error(f"Error while caching BunkerNet data : {err}")
        _exit(2)

    # Update db
    err = db.update_job_cache(
        "bunkernet-data",
        None,
        "ip.list",
        "\n".join(data["data"]).encode("utf-8"),
        checksum=new_hash,
    )
    if err:
        logger.warning(f"Couldn't update db cache: {err}")

    logger.info("Successfully saved BunkerNet data")

    status = 1

except:
    status = 2
    logger.error(f"Exception while running bunkernet-data.py :\n{format_exc()}")

sys_exit(status)
