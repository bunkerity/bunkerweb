#!/usr/bin/env python3

from datetime import date, datetime, timedelta
from gzip import decompress
from io import BytesIO
from os import sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from time import sleep
from typing import Optional

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="jobs-mmdb-asn",
    log_file_path="/var/log/bunkerweb/jobs.log"
)

logger.debug("Debug mode enabled for jobs-mmdb-asn")

from maxminddb import open_database
from requests import RequestException, Response, get
from requests.exceptions import ConnectionError

from common_utils import bytes_hash, file_hash  # type: ignore
from jobs import Job  # type: ignore

status = 0


# Request MMDB file information from db-ip.com to check for updates.
def request_mmdb() -> Optional[Response]:
    logger.debug("request_mmdb() called")
    try:
        max_retries = 3
        retry_count = 0
        logger.debug("Starting version check request to db-ip.com")
        
        while retry_count < max_retries:
            try:
                logger.debug(f"HTTP request attempt {retry_count + 1}/{max_retries}")
                response = get("https://db-ip.com/db/download/ip-to-asn-lite", timeout=5)
                logger.debug(f"Response received: status={response.status_code}")
                break
            except ConnectionError as e:
                retry_count += 1
                logger.debug(f"Connection error on attempt {retry_count}: {e}")
                if retry_count == max_retries:
                    raise e
                logger.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)
                
        response.raise_for_status()
        logger.debug("Version check request completed successfully")
        return response
    except RequestException as e:
        logger.exception("RequestException during version check")
        return None


try:
    logger.debug("Starting MMDB ASN download process")
    
    dl_mmdb = True
    tmp_path = Path(sep, "var", "tmp", "bunkerweb", "asn.mmdb")
    new_hash = None
    logger.debug(f"Temporary file path: {tmp_path}")

    # Don't go further if the cache match the latest version
    response = None
    if tmp_path.is_file():
        logger.debug("Temporary MMDB file exists, checking if it's the latest version")
        tmp_file_size = tmp_path.stat().st_size
        logger.debug(f"Temporary file size: {tmp_file_size} bytes")
        
        response = request_mmdb()

        if response and response.status_code == 200:
            current_hash = file_hash(tmp_path, algorithm="sha1")
            logger.debug(f"Current file hash: {current_hash}")
            
            if response.content.find(current_hash.encode()) != -1:
                logger.info("asn.mmdb is already the latest version, skipping download...")
                dl_mmdb = False
            else:
                logger.debug("File hash not found in response, update needed")
        else:
            logger.warning("Unable to check if the temporary mmdb file is the latest version, downloading it anyway...")

    logger.debug("Creating Job instance")
    JOB = Job(logger, __file__)

    if dl_mmdb:
        logger.debug("Checking job cache for existing MMDB file")
        job_cache = JOB.get_cache("asn.mmdb", with_info=True, with_data=True)
        logger.debug(f"Job cache result: {type(job_cache)}")
        
        if isinstance(job_cache, dict):
            skip_dl = True
            cache_size = len(job_cache.get("data", b""))
            cache_age = None
            
            if job_cache.get("last_update"):
                cache_age = datetime.now().astimezone().timestamp() - job_cache["last_update"]
                logger.debug(f"Cache file size: {cache_size} bytes, age: {cache_age:.0f} seconds")
            
            if response is None:
                logger.debug("No previous response, requesting version check")
                response = request_mmdb()

            if response and response.status_code == 200:
                cache_data = job_cache.get("data", b"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
                cache_hash = bytes_hash(cache_data, algorithm="sha1")
                skip_dl = response.content.find(cache_hash.encode()) != -1
                logger.debug(f"Cache hash check result: skip_dl={skip_dl}")
            elif job_cache.get("last_update") and job_cache["last_update"] < (datetime.now().astimezone() - timedelta(weeks=1)).timestamp():
                logger.warning("Unable to check if the cache file is the latest version from db-ip.com and file is older than 1 week, checking anyway...")
                skip_dl = False

            if skip_dl:
                logger.info("asn.mmdb is already the latest version and is cached, skipping...")
                sys_exit(0)

        # Compute the mmdb URL
        current_date = date.today()
        mmdb_url = f"https://download.db-ip.com/free/dbip-asn-lite-{current_date.strftime('%Y-%m')}.mmdb.gz"
        logger.debug(f"Generated MMDB URL: {mmdb_url}")

        # Download the mmdb file and save it to tmp
        logger.info(f"Downloading mmdb file from url {mmdb_url} ...")
        file_content = BytesIO()
        download_start_time = datetime.now()
        
        try:
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    logger.debug(f"Download attempt {retry_count + 1}/{max_retries}")
                    with get(mmdb_url, stream=True, timeout=5) as resp:
                        resp.raise_for_status()
                        content_length = resp.headers.get('content-length', 'unknown')
                        logger.debug(f"Response headers - Content-Length: {content_length}")
                        
                        downloaded_bytes = 0
                        for chunk in resp.iter_content(chunk_size=4 * 1024):
                            if chunk:
                                file_content.write(chunk)
                                downloaded_bytes += len(chunk)
                                
                        logger.debug(f"Downloaded {downloaded_bytes} bytes")
                    break
                except ConnectionError as e:
                    retry_count += 1
                    logger.debug(f"Connection error on download attempt {retry_count}: {e}")
                    if retry_count == max_retries:
                        raise e
                    logger.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                    sleep(3)

            assert file_content
            download_time = (datetime.now() - download_start_time).total_seconds()
            logger.debug(f"Download completed in {download_time:.2f} seconds")

            # Decompress it
            logger.info("Decompressing mmdb file ...")
            file_content.seek(0)
            compressed_size = len(file_content.getvalue())
            logger.debug(f"Compressed file size: {compressed_size} bytes")
            
            decompressed_data = decompress(file_content.getvalue())
            decompressed_size = len(decompressed_data)
            logger.debug(f"Decompressed file size: {decompressed_size} bytes")
            
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(decompressed_data)
            logger.debug(f"Written decompressed data to: {tmp_path}")

            if job_cache:
                # Check if file has changed
                new_hash = file_hash(tmp_path)
                old_hash = job_cache.get("checksum")
                logger.debug(f"File hash comparison: new={new_hash}, old={old_hash}")
                
                if new_hash == old_hash:
                    logger.info("New file is identical to cache file, reload is not needed")
                    sys_exit(0)
                else:
                    logger.debug("File hash changed, proceeding with cache update")
                    
        except BaseException as e:
            logger.exception(f"Error while downloading mmdb file from {mmdb_url}")
            if not tmp_path.is_file():
                sys_exit(2)
            logger.warning("Falling back to project cached mmdb file.")
            dl_mmdb = False

    # Try to load it
    logger.info("Checking if mmdb file is valid ...")
    if tmp_path.is_file():
        logger.debug(f"Validating MMDB file: {tmp_path}")
        try:
            with open_database(tmp_path.as_posix()) as reader:
                logger.debug("MMDB file validation successful")
                pass
        except Exception as e:
            logger.error(f"MMDB file validation failed: {e}")
            raise

    # Move it to cache folder
    logger.info("Moving mmdb file to cache ...")
    logger.debug(f"Caching file with hash: {new_hash}")
    cached, err = JOB.cache_file("asn.mmdb", tmp_path, checksum=new_hash)
    if not cached:
        logger.error(f"Error while caching mmdb file : {err}")
        sys_exit(2)
    else:
        logger.debug("MMDB file successfully cached")

    # Success
    if dl_mmdb:
        logger.info(f"Downloaded new mmdb from {mmdb_url}")
        logger.debug("MMDB download and caching process completed successfully")

    status = 1
except SystemExit as e:
    status = e.code
    logger.debug(f"SystemExit with code: {status}")
except BaseException as e:
    status = 2
    logger.exception("Exception while running mmdb-asn.py")

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
