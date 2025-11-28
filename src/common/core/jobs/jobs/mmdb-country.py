#!/usr/bin/env python3

from datetime import date, datetime, timedelta
from gzip import decompress
from io import BytesIO
from os import sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from maxminddb import open_database
from requests import RequestException, Response, get
from requests.exceptions import ConnectionError

from logger import getLogger  # type: ignore
from common_utils import bytes_hash, file_hash  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("JOBS.MMDB-COUNTRY")
status = 0


def request_mmdb() -> Optional[Response]:
    try:
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = get("https://db-ip.com/db/download/ip-to-country-lite", timeout=5)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)
        response.raise_for_status()
        return response
    except RequestException:
        LOGGER.debug(format_exc())
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

    JOB = Job(LOGGER, __file__)

    if dl_mmdb:
        job_cache = JOB.get_cache("country.mmdb", with_info=True, with_data=True)
        if isinstance(job_cache, dict):
            skip_dl = True
            if response is None:
                response = request_mmdb()

            if response and response.status_code == 200:
                skip_dl = response.content.find(bytes_hash(job_cache.get("data", b"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"), algorithm="sha1").encode()) != -1
            elif job_cache.get("last_update") and job_cache["last_update"] < (datetime.now().astimezone() - timedelta(weeks=1)).timestamp():
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
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    with get(mmdb_url, stream=True, timeout=5) as resp:
                        resp.raise_for_status()
                        for chunk in resp.iter_content(chunk_size=4 * 1024):
                            if chunk:
                                file_content.write(chunk)
                    break
                except ConnectionError as e:
                    retry_count += 1
                    if retry_count == max_retries:
                        raise e
                    LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                    sleep(3)

            assert file_content

            # Decompress it
            LOGGER.info("Decompressing mmdb file ...")
            file_content.seek(0)
            tmp_path.write_bytes(decompress(file_content.getvalue()))

            if job_cache:
                # Check if file has changed
                new_hash = file_hash(tmp_path)
                if new_hash == job_cache.get("checksum"):
                    LOGGER.info("New file is identical to cache file, reload is not needed")
                    sys_exit(0)
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while downloading mmdb file from {mmdb_url}: {e}")
            if not tmp_path.is_file():
                sys_exit(2)
            LOGGER.warning("Falling back to project cached mmdb file.")
            dl_mmdb = False

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
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running mmdb-country.py :\n{e}")

sys_exit(status)
