#!/usr/bin/python3

from datetime import date
from gzip import decompress
from hashlib import sha1
from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from maxminddb import open_database
from requests import RequestException, get

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import cache_file, cache_hash, file_hash, is_cached_file

logger = setup_logger("JOBS.mmdb-country", getenv("LOG_LEVEL", "INFO"))
status = 0
lock = Lock()

try:
    dl_mmdb = True
    tmp_path = Path(sep, "var", "tmp", "bunkerweb", "country.mmdb")
    cache_path = Path(sep, "var", "cache", "bunkerweb", "country.mmdb")
    new_hash = None

    # Don't go further if the cache match the latest version
    if tmp_path.exists():
        with lock:
            response = None
            try:
                response = get("https://db-ip.com/db/download/ip-to-country-lite", timeout=5)
            except RequestException:
                logger.warning("Unable to check if country.mmdb is the latest version")

        if response and response.status_code == 200:
            _sha1 = sha1()
            with open(str(tmp_path), "rb") as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    _sha1.update(data)

            if response.content.decode().find(_sha1.hexdigest()) != -1:
                logger.info("country.mmdb is already the latest version, skipping download...")
                dl_mmdb = False
        else:
            logger.warning("Unable to check if country.mmdb is the latest version, downloading it anyway...")

    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)

    if dl_mmdb:
        # Don't go further if the cache is fresh
        if is_cached_file(cache_path, "month", db):
            logger.info("country.mmdb is already in cache, skipping download...")
            _exit(0)

        # Compute the mmdb URL
        mmdb_url = f"https://download.db-ip.com/free/dbip-country-lite-{date.today().strftime('%Y-%m')}.mmdb.gz"

        # Download the mmdb file and save it to tmp
        logger.info(f"Downloading mmdb file from url {mmdb_url} ...")
        file_content = b""
        try:
            with get(mmdb_url, stream=True, timeout=5) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=4 * 1024):
                    if chunk:
                        file_content += chunk
        except RequestException:
            logger.error(f"Error while downloading mmdb file from {mmdb_url}")
            _exit(2)

        try:
            assert file_content
        except AssertionError:
            logger.error(f"Error while downloading mmdb file from {mmdb_url}")
            _exit(2)

        # Decompress it
        logger.info("Decompressing mmdb file ...")
        tmp_path.write_bytes(decompress(file_content))

        # Check if file has changed
        new_hash = file_hash(tmp_path)
        old_hash = cache_hash(cache_path, db)
        if new_hash == old_hash:
            logger.info("New file is identical to cache file, reload is not needed")
            _exit(0)

    # Try to load it
    logger.info("Checking if mmdb file is valid ...")
    with open_database(str(tmp_path)) as reader:
        pass

    # Move it to cache folder
    logger.info("Moving mmdb file to cache ...")
    cached, err = cache_file(tmp_path, cache_path, new_hash, db)
    if not cached:
        logger.error(f"Error while caching mmdb file : {err}")
        _exit(2)

    # Success
    if dl_mmdb:
        logger.info(f"Downloaded new mmdb from {mmdb_url}")

    status = 1
except:
    status = 2
    logger.error(f"Exception while running mmdb-country.py :\n{format_exc()}")

sys_exit(status)
