#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join, normpath
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from requests.exceptions import ConnectionError

from logger import setup_logger  # type: ignore
from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore


def check_line(line):
    with suppress(ValueError):
        if b"/" in line:
            ip_network(line.decode())
            return True, line
        else:
            ip_address(line.decode())
            return True, line
    return False, b""


LOGGER = setup_logger("REALIP")
REALIP_CACHE_PATH = join(sep, "var", "cache", "bunkerweb", "realip")
status = 0

try:
    # Check if at least a server has Realip activated
    realip_activated = False

    # Check if at least a server has Greylist activated
    greylist_activated = False

    services = getenv("SERVER_NAME", "www.example.com").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_realip_urls = {}

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_USE_REAL_IP", "no") == "yes":
                realip_activated = True

                # Get service URLs
                services_realip_urls[first_server] = set()
                for url in getenv(f"{first_server}_REAL_IP_FROM_URLS", "").strip().split(" "):
                    if url:
                        services_realip_urls[first_server].add(url)
    # Singlesite case
    elif getenv("USE_REAL_IP", "no") == "yes":
        realip_activated = True

    # Get global URLs
    services_realip_urls["global"] = set()
    for url in getenv("REAL_IP_FROM_URLS", "").strip().split(" "):
        if url:
            services_realip_urls["global"].add(url)

    if not realip_activated:
        LOGGER.info("RealIP is not activated, skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    if not any(services_realip_urls.values()):
        LOGGER.warning("No URL configured, nothing to do...")
        for file in list(JOB.job_path.rglob("*.list")):
            if file.parent == JOB.job_path:
                LOGGER.warning(f"Removing no longer used url file {file} ...")
                deleted, err = JOB.del_cache(file)
            else:
                LOGGER.warning(f"Removing no longer used service file {file} ...")
                deleted, err = JOB.del_cache(file, service_id=file.parent.name)

            if not deleted:
                LOGGER.warning(f"Couldn't delete file {file} from cache : {err}")
        sys_exit(0)

    urls = set()
    failed_urls = set()
    processed_urls = set()  # Track which URLs have been processed globally
    # Initialize aggregation per kind with service tracking
    aggregated_recap = {
        "total_services": set(),
        "total_urls": 0,
        "downloaded_urls": 0,
        "skipped_urls": 0,
        "failed_count": 0,
        "total_lines": 0,
    }

    for service, urls_list in services_realip_urls.items():
        # Track that this service provided URLs for the current kind
        if service != "global":
            aggregated_recap["total_services"].add(service)

        # Use set to avoid duplicate entries
        unique_entries = set()
        content = b""
        for url in urls_list:
            url_file = f"{bytes_hash(url, algorithm='sha1')}.list"
            cached_url = JOB.get_cache(url_file, with_info=True, with_data=True)
            try:
                # Only count URLs that haven't been processed globally
                if url not in processed_urls:
                    aggregated_recap["total_urls"] += 1

                # If the URL has recently been downloaded, use cache
                if url in failed_urls:
                    if url not in processed_urls:
                        aggregated_recap["failed_count"] += 1
                elif (
                    isinstance(cached_url, dict)
                    and cached_url.get("last_update")
                    and cached_url["last_update"] > (datetime.now().astimezone() - timedelta(hours=1)).timestamp()
                ):
                    LOGGER.debug(f"URL {url} has already been downloaded less than 1 hour ago, skipping download...")
                    if url not in processed_urls:
                        aggregated_recap["skipped_urls"] += 1
                    # Process cached data and add to unique_entries
                    cached_data = cached_url.get("data", b"")
                    if cached_data:
                        # Skip first line (URL comment) and process entries
                        for line in cached_data.split(b"\n")[1:]:
                            line = line.strip()
                            if line:
                                unique_entries.add(line)
                else:
                    LOGGER.info(f"Downloading Real IP data from {url} ...")
                    failed = False
                    if url.startswith("file://"):
                        try:
                            with open(normpath(url[7:]), "rb") as f:
                                iterable = f.readlines()
                        except OSError as e:
                            status = 2
                            LOGGER.debug(format_exc())
                            LOGGER.error(f"Error while opening file {url[7:]} : {e}")
                            failed_urls.add(url)
                            if url_file not in urls:
                                aggregated_recap["failed_count"] += 1
                            failed = True
                    else:
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                resp = get(url, stream=True, timeout=10)
                                break
                            except ConnectionError as e:
                                retry_count += 1
                                if retry_count == max_retries:
                                    raise e
                                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                                sleep(3)

                        if resp.status_code != 200:
                            status = 2
                            LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                            failed_urls.add(url)
                            if url_file not in urls:
                                aggregated_recap["failed_count"] += 1
                            failed = True
                        else:
                            iterable = resp.iter_lines()

                    if not failed:
                        if url not in processed_urls:
                            aggregated_recap["downloaded_urls"] += 1

                        url_content = b""
                        count_lines = 0
                        for line in iterable:
                            line = line.strip()
                            if not line or line.startswith((b"#", b";")):
                                continue
                            ok, data = check_line(line)
                            if ok:
                                unique_entries.add(data)
                                url_content += data + b"\n"
                                count_lines += 1
                        if url not in processed_urls:
                            aggregated_recap["total_lines"] += count_lines

                        cached, err = JOB.cache_file(url_file, b"# Downloaded from " + url.encode("utf-8") + b"\n" + url_content)
                        if not cached:
                            LOGGER.error(f"Error while caching url content for {url}: {err}")
            except BaseException as e:
                status = 2
                LOGGER.debug(format_exc())
                LOGGER.error(f"Exception while getting {service} greylist from {url} :\n{e}")
                failed_urls.add(url)
                if url not in processed_urls:
                    aggregated_recap["failed_count"] += 1
            finally:
                # Mark URL as processed to avoid double counting
                processed_urls.add(url)
                urls.add(url_file)

        # Build final content from unique entries, sorted for consistency
        content = b"\n".join(sorted(unique_entries)) + b"\n" if unique_entries else b""

        if not content:
            continue

        # Check if file has changed
        new_hash = bytes_hash(content)
        old_hash = JOB.cache_hash("combined.list", service_id="" if service == "global" else service)
        if new_hash == old_hash:
            LOGGER.debug(f"{service} file combined.list is identical to cache file, reload is not needed")
            continue
        elif old_hash:
            LOGGER.debug(f"{service} file combined.list is different than cache file, reload is needed")
        else:
            LOGGER.debug(f"New {service} file combined.list is not in cache, reload is needed")

        # Put file in cache
        cached, err = JOB.cache_file("combined.list", content, service_id="" if service == "global" else service, checksum=new_hash)
        if not cached:
            LOGGER.error(f"Error while caching combined list for {service} : {err}")
            status = 2
            continue

        status = 1 if status != 2 else 2

    # Log a detailed recap per kind across services, only if there is at least one service using the kind
    service_count = len(aggregated_recap["total_services"])
    if service_count:
        successful = aggregated_recap["downloaded_urls"]
        skipped = aggregated_recap["skipped_urls"]
        failed = aggregated_recap["failed_count"]
        total_lines = aggregated_recap["total_lines"]
        LOGGER.info(
            f"Recap for combined.list urls: Total Services: {service_count}, Successful: {successful}, "
            f"Skipped (cached): {skipped}, Failed: {failed}, Total Lines: {total_lines}"
        )

    # Remove old files
    for url_file in JOB.job_path.glob("*.list"):
        if url_file.name == "combined.list":
            continue

        LOGGER.debug(f"Checking if {url_file} is still in use ...")
        if url_file.name not in urls:
            LOGGER.warning(f"Removing no longer used url file {url_file} ...")
            deleted, err = JOB.del_cache(url_file)
            if not deleted:
                LOGGER.warning(f"Couldn't delete url file {url_file} from cache : {err}")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running realip-download.py :\n{e}")

sys_exit(status)
