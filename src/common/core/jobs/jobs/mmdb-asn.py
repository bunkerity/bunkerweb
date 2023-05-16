#!/usr/bin/python3

from datetime import date
from gzip import decompress
from hashlib import sha1
from os import _exit, getenv
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
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
    dl_mmdb = True
    tmp_path = "/var/tmp/bunkerweb/asn.mmdb"
    new_hash = None

    # Don't go further if the cache match the latest version
    if Path("/var/tmp/bunkerweb/asn.mmdb").exists():
        response = get("https://db-ip.com/db/download/ip-to-asn-lite")

        if response.status_code == 200:
            _sha1 = sha1()
            with open("/var/tmp/bunkerweb/asn.mmdb", "rb") as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    _sha1.update(data)

            if response.content.decode().find(_sha1.hexdigest()) != -1:
                logger.info(
                    "asn.mmdb is already the latest version, skipping download..."
                )
                dl_mmdb = False
                tmp_path = "/var/tmp/bunkerweb/asn.mmdb"
        else:
            logger.warning(
                "Unable to check if asn.mmdb is the latest version, downloading it anyway..."
            )

    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )

    if dl_mmdb:
        # Don't go further if the cache is fresh
        if is_cached_file("/var/cache/bunkerweb/asn.mmdb", "month", db):
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
        Path(tmp_path).write_bytes(decompress(file_content))

        # Check if file has changed
        new_hash = file_hash(tmp_path)
        old_hash = cache_hash("/var/cache/bunkerweb/asn.mmdb", db)
        if new_hash == old_hash:
            logger.info("New file is identical to cache file, reload is not needed")
            _exit(0)

    # Try to load it
    logger.info("Checking if mmdb file is valid ...")
    with open_database(tmp_path or "/var/cache/bunkerweb/asn.mmdb") as reader:
        pass

    # Move it to cache folder
    logger.info("Moving mmdb file to cache ...")
    cached, err = cache_file(tmp_path, "/var/cache/bunkerweb/asn.mmdb", new_hash, db)
    if not cached:
        logger.error(f"Error while caching mmdb file : {err}")
        _exit(2)

    # Success
    if dl_mmdb:
        logger.info(f"Downloaded new mmdb from {mmdb_url}")

    status = 1

except:
    status = 2
    logger.error(f"Exception while running mmdb-asn.py :\n{format_exc()}")

sys_exit(status)
