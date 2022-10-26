#!/usr/bin/python3

from datetime import date
from gzip import decompress
from os import _exit, getenv
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/db")

from maxminddb import open_database
from requests import get

from Database import Database
from logger import setup_logger
from jobs import cache_file, cache_hash, file_hash, is_cached_file

logger = setup_logger("JOBS", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
    bw_integration="Kubernetes"
    if getenv("KUBERNETES_MODE", "no") == "yes"
    else "Cluster",
)
status = 0

try:
    # Don't go further if the cache is fresh
    if is_cached_file("/opt/bunkerweb/cache/asn.mmdb", "month"):
        logger.info("asn.mmdb is already in cache, skipping download...")
        _exit(0)

    # Compute the mmdb URL
    today = date.today()
    mmdb_url = "https://download.db-ip.com/free/dbip-asn-lite-{}-{}.mmdb.gz".format(
        today.strftime("%Y"), today.strftime("%m")
    )

    # Download the mmdb file
    logger.info(f"Downloading mmdb file from url {mmdb_url} ...")
    resp = get(mmdb_url)

    # Save it to temp
    logger.info("Saving mmdb file to tmp ...")
    with open("/opt/bunkerweb/tmp/asn.mmdb", "wb") as f:
        f.write(decompress(resp.content))

    # Try to load it
    logger.info("Checking if mmdb file is valid ...")
    with open_database("/opt/bunkerweb/tmp/asn.mmdb") as reader:
        pass

    # Check if file has changed
    new_hash = file_hash("/opt/bunkerweb/tmp/asn.mmdb")
    old_hash = cache_hash("/opt/bunkerweb/cache/asn.mmdb")
    if new_hash == old_hash:
        logger.info("New file is identical to cache file, reload is not needed")
        _exit(0)

    # Move it to cache folder
    logger.info("Moving mmdb file to cache ...")
    cached, err = cache_file(
        "/opt/bunkerweb/tmp/asn.mmdb", "/opt/bunkerweb/cache/asn.mmdb", new_hash
    )
    if not cached:
        logger.error(f"Error while caching mmdb file : {err}")
        _exit(2)

    # Update db
    err = db.update_job_cache(
        "mmdb-asn", None, "asn.mmdb", resp.content, checksum=new_hash
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
