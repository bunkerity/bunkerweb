#!/usr/bin/python3

from datetime import date
from gzip import decompress
from os import _exit, getenv
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/db",
    )
)

from requests import get
from maxminddb import open_database

from Database import Database
from logger import setup_logger
from jobs import cache_file, cache_hash, file_hash, is_cached_file

logger = setup_logger("JOBS", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
lock = Lock()
status = 0

try:
    # Don't go further if the cache is fresh
    if is_cached_file("/var/cache/bunkerweb/country.mmdb", "month"):
        logger.info("country.mmdb is already in cache, skipping download...")
        _exit(0)

    # Compute the mmdb URL
    mmdb_url = f"https://download.db-ip.com/free/dbip-country-lite-{date.today().strftime('%Y-%m')}.mmdb.gz"

    # Download the mmdb file
    logger.info(f"Downloading mmdb file from url {mmdb_url} ...")
    resp = get(mmdb_url)

    # Save it to temp
    logger.info("Saving mmdb file to tmp ...")
    Path(f"/var/tmp/bunkerweb/country.mmdb").write_bytes(decompress(resp.content))

    # Try to load it
    logger.info("Checking if mmdb file is valid ...")
    with open_database("/var/tmp/bunkerweb/country.mmdb") as reader:
        pass

    # Check if file has changed
    new_hash = file_hash("/var/tmp/bunkerweb/country.mmdb")
    old_hash = cache_hash("/var/cache/bunkerweb/country.mmdb")
    if new_hash == old_hash:
        logger.info("New file is identical to cache file, reload is not needed")
        _exit(0)

    # Move it to cache folder
    logger.info("Moving mmdb file to cache ...")
    cached, err = cache_file(
        "/var/tmp/bunkerweb/country.mmdb",
        "/var/cache/bunkerweb/country.mmdb",
        new_hash,
    )
    if not cached:
        logger.error(f"Error while caching mmdb file : {err}")
        _exit(2)

    # Update db
    with lock:
        err = db.update_job_cache(
            "mmdb-country", None, "country.mmdb", resp.content, checksum=new_hash
        )

    if err:
        logger.warning(f"Couldn't update db cache: {err}")

    # Success
    logger.info(f"Downloaded new mmdb from {mmdb_url}")

    status = 1

except:
    status = 2
    logger.error(f"Exception while running mmdb-country.py :\n{format_exc()}")

sys_exit(status)
