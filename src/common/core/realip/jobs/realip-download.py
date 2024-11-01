#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join, normpath
from sys import exit as sys_exit, path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

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


LOGGER = setup_logger("REALIP", getenv("LOG_LEVEL", "INFO"))
REALIP_CACHE_PATH = join(sep, "var", "cache", "bunkerweb", "realip")
status = 0

try:
    # Check if at least a server has Realip activated
    realip_activated = False

    # Check if at least a server has Greylist activated
    greylist_activated = False

    services = getenv("SERVER_NAME", "").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_realip_urls = {}

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_USE_REAL_IP", getenv("USE_REAL_IP", "no")) == "yes":
                realip_activated = True

                # Get URLs
                services_realip_urls[first_server] = set()
                for url in getenv(f"{first_server}_REAL_IP_FROM_URLS", getenv("REAL_IP_FROM_URLS", "")).strip().split(" "):
                    if url:
                        services_realip_urls[first_server].add(url)
    # Singlesite case
    elif getenv("USE_REAL_IP", "no") == "yes":
        realip_activated = True

        # Get URLs
        services_realip_urls[services[0]] = set()
        for url in getenv("REAL_IP_FROM_URLS", "").strip().split(" "):
            if url:
                services_realip_urls[services[0]].add(url)

    if not realip_activated:
        LOGGER.info("RealIP is not activated, skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER)

    if not any(services_realip_urls.values()):
        LOGGER.warning("No URL configured, nothing to do...")
        for file in JOB.job_path.rglob("*.list"):
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

    for service, urls in services_realip_urls.items():
        if not urls:
            if JOB.job_path.joinpath(service, "combined.list").is_file():
                LOGGER.warning(f"{service} realip combined.list is cached but no URL is configured, removing from cache...")
                deleted, err = JOB.del_cache("combined.list", service_id=service)
                if not deleted:
                    LOGGER.warning(f"Couldn't delete {service} combined.list from cache : {err}")
            continue

        # Write combined data of the kind in memory and check if it has changed
        content = b""
        for url in urls:
            url_file = f"{bytes_hash(url, algorithm='sha1')}.list"
            urls.add(url_file)
            cached_url = JOB.get_cache(url_file, with_info=True, with_data=True)
            try:
                # Check if the URL has already been downloaded
                if url in failed_urls:
                    continue
                elif isinstance(cached_url, dict) and cached_url["last_update"] < (datetime.now().astimezone() - timedelta(hours=1)).timestamp():
                    LOGGER.info(f"URL {url} has already been downloaded less than 1 hour ago, skipping download...")
                    # Remove first line (URL) and add to content
                    content += b"\n".join(cached_url["data"].split(b"\n")[1:]) + b"\n"
                else:
                    LOGGER.info(f"Downloading realip data from {url} ...")
                    if url.startswith("file://"):
                        with open(normpath(url[7:]), "rb") as f:
                            iterable = f.readlines()
                    else:
                        resp = get(url, stream=True, timeout=10)

                        if resp.status_code != 200:
                            LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                            continue

                        iterable = resp.iter_lines()

                    i = 0
                    for line in iterable:
                        line = line.strip().split(b" ")[0]

                        if not line or line.startswith((b"#", b";")):
                            continue

                        ok, data = check_line(line)
                        if ok:
                            content += data + b"\n"
                            i += 1

                    LOGGER.info(f"Downloaded {i} realip from {url}")

                    cached, err = JOB.cache_file(url_file, b"# Downloaded from " + url.encode("utf-8") + b"\n" + content)
                    if not cached:
                        LOGGER.error(f"Error while caching url content : {err}")
            except BaseException as e:
                status = 2
                LOGGER.error(f"Exception while getting {service} realip from {url} :\n{e}")
                failed_urls.add(url)

        LOGGER.debug(f"Content for {service} : {content}")

        # Check if file has changed
        new_hash = bytes_hash(content)
        old_hash = JOB.cache_hash("combined.list", service_id=service)
        if new_hash == old_hash:
            LOGGER.info(f"New {service} file combined.list is identical to cache file, reload is not needed")
            continue

        LOGGER.info(f"New {service} file combined.list is different than cache file, reload is needed")
        # Put file in cache
        cached, err = JOB.cache_file("combined.list", content, service_id=service, checksum=new_hash)
        if not cached:
            LOGGER.error(f"Error while caching realip : {err}")
            status = 2
            continue

        status = 1

    # Remove old files
    for url_file in JOB.job_path.glob("*.list"):
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
    LOGGER.error(f"Exception while running realip-download.py :\n{e}")

sys_exit(status)
