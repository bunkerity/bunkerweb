#!/usr/bin/python3

from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("db",),
        ("core", "bunkernet", "jobs"),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import data
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import cache_file, cache_hash, file_hash, is_cached_file, get_file_in_db

logger = setup_logger("BUNKERNET", getenv("LOG_LEVEL", "INFO"))
exit_status = 0

try:
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if (
                getenv(f"{first_server}_USE_BUNKERNET", getenv("USE_BUNKERNET", "yes"))
                == "yes"
            ):
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True

    if not bunkernet_activated:
        logger.info("BunkerNet is not activated, skipping download...")
        _exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)
    bunkernet_tmp_path = Path(sep, "var", "tmp", "bunkerweb", "bunkernet")
    bunkernet_tmp_path.mkdir(parents=True, exist_ok=True)

    # Create empty file in case it doesn't exist
    if not bunkernet_path.joinpath("ip.list").is_file():
        bunkernet_path.joinpath("ip.list").write_text("")

    # Get ID from cache
    bunkernet_id = None
    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    bunkernet_id = get_file_in_db("instance.id", db)
    if bunkernet_id:
        bunkernet_path.joinpath("bunkernet.id").write_bytes(bunkernet_id)
        logger.info("Successfully retrieved BunkerNet ID from db cache")
    else:
        logger.info("No BunkerNet ID found in db cache")

    # Check if ID is present
    if not bunkernet_path.joinpath("instance.id").is_file():
        logger.error(
            "Not downloading BunkerNet data because instance is not registered",
        )
        _exit(2)

    # Don't go further if the cache is fresh
    if is_cached_file(bunkernet_path.joinpath("ip.list"), "day", db):
        logger.info(
            "BunkerNet list is already in cache, skipping download...",
        )
        _exit(0)

    exit_status = 1

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
    elif status == 403:
        logger.warning(
            "BunkerNet has banned this instance, retrying a register later...",
        )
        _exit(0)

    try:
        assert isinstance(data, dict)
    except AssertionError:
        logger.error(
            f"Received invalid data from BunkerNet API while sending db request : {data}",
        )
        _exit(2)

    if data["result"] != "ok":
        logger.error(
            f"Received error from BunkerNet API while sending db request : {data['data']}, removing instance ID",
        )
        _exit(2)

    logger.info("Successfully downloaded data from BunkerNet API")

    # Writing data to file
    logger.info("Saving BunkerNet data ...")
    content = "\n".join(data["data"]).encode("utf-8")
    bunkernet_tmp_path.joinpath("ip.list").write_bytes(content)

    # Check if file has changed
    new_hash = file_hash(bunkernet_tmp_path.joinpath("ip.list"))
    old_hash = cache_hash(bunkernet_path.joinpath("ip.list"), db)
    if new_hash == old_hash:
        logger.info(
            "New file is identical to cache file, reload is not needed",
        )
        _exit(0)

    # Put file in cache
    cached, err = cache_file(
        bunkernet_tmp_path.joinpath("ip.list"),
        bunkernet_path.joinpath("ip.list"),
        new_hash,
        db,
    )
    if not cached:
        logger.error(f"Error while caching BunkerNet data : {err}")
        _exit(2)

    logger.info("Successfully saved BunkerNet data")

    exit_status = 1
except:
    exit_status = 2
    logger.error(f"Exception while running bunkernet-data.py :\n{format_exc()}")

sys_exit(exit_status)
