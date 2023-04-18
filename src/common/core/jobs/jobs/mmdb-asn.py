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

from maxminddb import open_database
from requests import get

from Database import Database
from logger import setup_logger
from jobs import cache_file, cache_hash, file_hash, is_cached_file

logger = setup_logger("JOBS.mmdb-asn", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Don't go further if the cache is fresh
    if is_cached_file("/var/cache/bunkerweb/asn.mmdb", "month"):
        logger.info("asn.mmdb is already in cache, skipping download...")
        _exit(0)

    # Compute the mmdb URL
    mmdb_url = f"https://download.db-ip.com/free/dbip-asn-lite-{date.today().strftime('%Y-%m')}.mmdb.gz"

    # Download the mmdb file and save it to tmp
    logger.info(f"Downloading mmdb file from url {mmdb_url} ...")
    file_content = b""
    with get(mmdb_url, stream=True) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=4 * 1024):
            if chunk:
                file_content += chunk

    try:
        assert file_content
    except AssertionError:
        logger.error(f"Error while downloading mmdb file from {mmdb_url}")
        _exit(2)

    # Decompress it
    logger.info("Decompressing mmdb file ...")
    file_content = decompress(file_content)
    Path(f"/var/tmp/bunkerweb/asn.mmdb").write_bytes(file_content)

    # Try to load it
    logger.info("Checking if mmdb file is valid ...")
    with open_database("/var/tmp/bunkerweb/asn.mmdb") as reader:
        pass

    # Check if file has changed
    new_hash = file_hash("/var/tmp/bunkerweb/asn.mmdb")
    old_hash = cache_hash("/var/cache/bunkerweb/asn.mmdb")
    if new_hash == old_hash:
        logger.info("New file is identical to cache file, reload is not needed")
        _exit(0)

    # Move it to cache folder
    logger.info("Moving mmdb file to cache ...")
    cached, err = cache_file(
        "/var/tmp/bunkerweb/asn.mmdb", "/var/cache/bunkerweb/asn.mmdb", new_hash
    )
    if not cached:
        logger.error(f"Error while caching mmdb file : {err}")
        _exit(2)

    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    lock = Lock()

    # Update db
    with lock:
        err = db.update_job_cache(
            "mmdb-asn", None, "asn.mmdb", file_content, checksum=new_hash
        )

    if err:
        logger.warning(f"Couldn't update db cache: {err}")

    # Success
    logger.info(f"Downloaded new mmdb from {mmdb_url}")

    status = 1

except:
    status = 2
    logger.error(f"Exception while running mmdb-asn.py :\n{format_exc()}")

sys_exit(status)
