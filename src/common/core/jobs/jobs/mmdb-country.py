#!/usr/bin/env python3

from datetime import date, datetime, timedelta
from gzip import decompress
from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from maxminddb import open_database
from requests import RequestException, Response, get

from logger import setup_logger  # type: ignore
from common_utils import bytes_hash, file_hash  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("JOBS.mmdb-country", getenv("LOG_LEVEL", "INFO"))
status = 0


def request_mmdb() -> Optional[Response]:
    try:
        response = get("https://db-ip.com/db/download/ip-to-country-lite", timeout=5)
        response.raise_for_status()
        return response
    except RequestException:
        return None


try:
    dl_mmdb = True
    tmp_path = Path(sep, "var", "tmp", "bunkerweb", "country.mmdb")
    new_hash = None

    # Don't go further if the cache match the latest version
    response = None
    if tmp_path.is_file():
        response = request_mmdb()

        if response and response.status_code == 200:
            if response.content.find(file_hash(tmp_path, algorithm="sha1").encode()) != -1:
                LOGGER.info("country.mmdb is already the latest version, skipping download...")
                dl_mmdb = False
        else:
            LOGGER.warning("Unable to check if the temporary mmdb file is the latest version, downloading it anyway...")

    JOB = Job(LOGGER)

    if dl_mmdb:
        job_cache = JOB.get_cache("country.mmdb", with_info=True, with_data=True)
        if isinstance(job_cache, dict):
            skip_dl = True
            if response is None:
                response = request_mmdb()

            if response and response.status_code == 200:
                skip_dl = response.content.find(bytes_hash(job_cache["data"], algorithm="sha1").encode()) != -1
            elif job_cache["last_update"] < (datetime.now() - timedelta(weeks=1)).timestamp():
                LOGGER.warning("Unable to check if the cache file is the latest version from db-ip.com and file is older than 1 week, checking anyway...")
                skip_dl = False

            if skip_dl:
                LOGGER.info("country.mmdb is already the latest version and is cached, skipping...")
                sys_exit(0)

        # Compute the mmdb URL
        mmdb_url = f"https://download.db-ip.com/free/dbip-country-lite-{date.today().strftime('%Y-%m')}.mmdb.gz"

        # Download the mmdb file and save it to tmp
        LOGGER.info(f"Downloading mmdb file from url {mmdb_url} ...")
        file_content = BytesIO()
        try:
            with get(mmdb_url, stream=True, timeout=5) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=4 * 1024):
                    if chunk:
                        file_content.write(chunk)
        except RequestException as e:
            LOGGER.error(f"Error while downloading mmdb file from {mmdb_url}: {e}")
            sys_exit(2)

        try:
            assert file_content
        except AssertionError:
            LOGGER.error(f"Error while downloading mmdb file from {mmdb_url}")
            sys_exit(2)

        # Decompress it
        LOGGER.info("Decompressing mmdb file ...")
        file_content.seek(0)
        tmp_path.write_bytes(decompress(file_content.getvalue()))

        if job_cache:
            # Check if file has changed
            new_hash = file_hash(tmp_path)
            if new_hash == job_cache["checksum"]:
                LOGGER.info("New file is identical to cache file, reload is not needed")
                sys_exit(0)

    # Try to load it
    LOGGER.info("Checking if mmdb file is valid ...")
    if tmp_path.is_file():
        with open_database(tmp_path.as_posix()) as reader:
            pass

    # Move it to cache folder
    LOGGER.info("Moving mmdb file to cache ...")
    cached, err = JOB.cache_file("country.mmdb", tmp_path, checksum=new_hash)
    if not cached:
        LOGGER.error(f"Error while caching mmdb file : {err}")
        sys_exit(2)

    # Success
    if dl_mmdb:
        LOGGER.info(f"Downloaded new mmdb from {mmdb_url}")

    status = 1
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running mmdb-country.py :\n{format_exc()}")

sys_exit(status)
