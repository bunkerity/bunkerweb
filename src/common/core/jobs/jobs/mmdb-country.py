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
        ("api",),
        ("utils",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from maxminddb import open_database
from requests import RequestException, get

from API import API  # type: ignore
from logger import setup_logger  # type: ignore

from jobs import cache_file, cache_hash, file_hash, is_cached_file

LOGGER = setup_logger("JOBS.mmdb-country", getenv("LOG_LEVEL", "INFO"))
CORE_API = API(getenv("API_ADDR", ""), "job-mmdb-country")
CORE_TOKEN = getenv("CORE_TOKEN", None)
status = 0
lock = Lock()

try:
    # Don't go further if the cache is fresh
    in_cache, is_cached = is_cached_file("country.mmdb", "month", CORE_API, CORE_TOKEN)
    if is_cached:
        LOGGER.info("country.mmdb is already in cache, skipping cache update...")
        _exit(0)

    dl_mmdb = True
    tmp_path = Path(sep, "var", "tmp", "bunkerweb", "country.mmdb")
    new_hash = None

    # Don't go further if the cache match the latest version
    if tmp_path.exists():
        with lock:
            response = None
            try:
                response = get("https://db-ip.com/db/download/ip-to-country-lite", timeout=5)
            except RequestException:
                LOGGER.warning("Unable to check if country.mmdb is the latest version")

        if response and response.status_code == 200:
            _sha1 = sha1()
            with open(str(tmp_path), "rb") as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    _sha1.update(data)

            if response.content.decode().find(_sha1.hexdigest()) != -1:
                LOGGER.info("country.mmdb is already the latest version, skipping download...")
                dl_mmdb = False
        else:
            LOGGER.warning("Unable to check if country.mmdb is the latest version, downloading it anyway...")

    if dl_mmdb:
        # Compute the mmdb URL
        mmdb_url = f"https://download.db-ip.com/free/dbip-country-lite-{date.today().strftime('%Y-%m')}.mmdb.gz"

        # Download the mmdb file and save it to tmp
        LOGGER.info(f"Downloading mmdb file from url {mmdb_url} ...")
        file_content = b""
        try:
            with get(mmdb_url, stream=True, timeout=5) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=4 * 1024):
                    if chunk:
                        file_content += chunk
        except RequestException:
            LOGGER.error(f"Error while downloading mmdb file from {mmdb_url}")
            _exit(2)

        try:
            assert file_content
        except AssertionError:
            LOGGER.error(f"Error while downloading mmdb file from {mmdb_url}")
            _exit(2)

        # Decompress it
        LOGGER.info("Decompressing mmdb file ...")
        tmp_path.write_bytes(decompress(file_content))

    if in_cache:
        # Check if file has changed
        new_hash = file_hash(tmp_path)
        old_hash = cache_hash("country.mmdb", CORE_API, CORE_TOKEN)
        if new_hash == old_hash:
            LOGGER.info("New file is identical to cache file, reload is not needed")
            _exit(0)

    # Try to load it
    LOGGER.info("Checking if mmdb file is valid ...")
    with open_database(str(tmp_path)) as reader:
        pass

    # Move it to cache folder
    LOGGER.info("Moving mmdb file to cache ...")
    cached, err = cache_file("country.mmdb", tmp_path, CORE_API, CORE_TOKEN, checksum=new_hash)
    if not cached:
        LOGGER.error(f"Error while caching mmdb file : {err}")
        _exit(2)

    # Success
    if dl_mmdb:
        LOGGER.info(f"Downloaded new mmdb from {mmdb_url}")

    status = 1
except:
    status = 2
    LOGGER.error(f"Exception while running mmdb-country.py :\n{format_exc()}")

sys_exit(status)
