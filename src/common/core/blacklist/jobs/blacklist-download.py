#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join, normpath
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from typing import Tuple

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from common_utils import bytes_hash  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

rdns_rx = re_compile(rb"^[^ ]+$")
asn_rx = re_compile(rb"^\d+$")
uri_rx = re_compile(rb"^/")


def check_line(kind: str, line: bytes) -> Tuple[bool, bytes]:
    if kind in ("IP", "IGNORE_IP"):
        if b"/" in line:
            with suppress(ValueError):
                ip_network(line.decode("utf-8"))
                return True, line
        else:
            with suppress(ValueError):
                ip_address(line.decode("utf-8"))
                return True, line
    elif kind in ("RDNS", "IGNORE_RDNS"):
        if rdns_rx.match(line):
            return True, line.lower()
    elif kind in ("ASN", "IGNORE_ASN"):
        real_line = line.replace(b"AS", b"").replace(b"as", b"")
        if asn_rx.match(real_line):
            return True, real_line
    elif kind in ("USER_AGENT", "IGNORE_USER_AGENT"):
        return True, b"(?:\\b)" + line + b"(?:\\b)"
    elif kind in ("URI", "IGNORE_URI"):
        if uri_rx.match(line):
            return True, line

    return False, b""


LOGGER = setup_logger("BLACKLIST", getenv("LOG_LEVEL", "INFO"))
status = 0

KINDS = ("IP", "RDNS", "ASN", "USER_AGENT", "URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT", "IGNORE_URI")

try:
    # Check if at least a server has Blacklist activated
    blacklist_activated = False

    services = getenv("SERVER_NAME", "").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_blacklist_urls = {}

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_USE_BLACKLIST", getenv("USE_BLACKLIST", "yes")) == "yes":
                blacklist_activated = True

                # Get services URLs
                services_blacklist_urls[first_server] = {}
                for kind in KINDS:
                    services_blacklist_urls[first_server][kind] = set()
                    for url in getenv(f"{first_server}_BLACKLIST_{kind}_URLS", getenv(f"BLACKLIST_{kind}_URLS", "")).strip().split(" "):
                        if url:
                            services_blacklist_urls[first_server][kind].add(url)
    # Singlesite case
    elif getenv("USE_BLACKLIST", "yes") == "yes":
        blacklist_activated = True

        # Get global URLs
        services_blacklist_urls[services[0]] = {}
        for kind in KINDS:
            services_blacklist_urls[services[0]][kind] = set()
            for url in getenv(f"BLACKLIST_{kind}_URLS", "").strip().split(" "):
                if url:
                    services_blacklist_urls[services[0]][kind].add(url)

    if not blacklist_activated:
        LOGGER.info("Blacklist is not activated, skipping downloads...")
        sys_exit(0)

    JOB = Job(LOGGER)

    if not any(url for urls in services_blacklist_urls.values() for url in urls.values()):
        LOGGER.warning("No blacklist URL is configured, nothing to do...")
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

    # Loop on kinds
    for service, kinds in services_blacklist_urls.items():
        for kind, urls_list in kinds.items():
            if not urls_list:
                if JOB.job_path.joinpath(service, f"{kind}.list").is_file():
                    LOGGER.warning(f"{service} blacklist for {kind} is cached but no URL is configured, removing from cache...")
                    deleted, err = JOB.del_cache(f"{kind}.list", service_id=service)
                    if not deleted:
                        LOGGER.warning(f"Couldn't delete {service} {kind}.list from cache : {err}")
                continue

            # Write combined data of the kind in memory and check if it has changed
            content = b""
            for url in urls_list:
                url_file = f"{bytes_hash(url, algorithm='sha1')}.list"
                urls.add(url_file)
                cached_url = JOB.get_cache(url_file, with_info=True, with_data=True)
                try:
                    # Check if the URL has already been downloaded
                    if url in failed_urls:
                        continue
                    elif isinstance(cached_url, dict) and cached_url["last_update"] > (datetime.now().astimezone() - timedelta(hours=1)).timestamp():
                        LOGGER.info(f"URL {url} has already been downloaded less than 1 hour ago, skipping download...")
                        # Remove first line (URL) and add to content
                        content += b"\n".join(cached_url["data"].split(b"\n")[1:]) + b"\n"
                    else:
                        LOGGER.info(f"Downloading blacklist data from {url} ...")
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
                            line = line.strip()

                            if not line or line.startswith((b"#", b";")):
                                continue
                            elif kind != "USER_AGENT":
                                line = line.split(b" ")[0]

                            ok, data = check_line(kind, line)
                            if ok:
                                content += data + b"\n"
                                i += 1

                        LOGGER.info(f"Downloaded {i} bad {kind}")

                        cached, err = JOB.cache_file(url_file, b"# Downloaded from " + url.encode("utf-8") + b"\n" + content)
                        if not cached:
                            LOGGER.error(f"Error while caching url content : {err}")
                except BaseException as e:
                    status = 2
                    LOGGER.error(f"Exception while getting {service} blacklist from {url} :\n{e}")
                    failed_urls.add(url)

            if not content:
                LOGGER.warning(f"No data for {service} {kind}, skipping...")
                continue

            # Check if file has changed
            new_hash = bytes_hash(content)
            old_hash = JOB.cache_hash(f"{kind}.list", service_id=service)
            if new_hash == old_hash:
                LOGGER.info(f"New {service} file {kind}.list is identical to cache file, reload is not needed")
                continue
            elif old_hash:
                LOGGER.info(f"New {service} file {kind}.list is different than cache file, reload is needed")
            else:
                LOGGER.info(f"New {service} file {kind}.list is not in cache, reload is needed")

            # Put file in cache
            cached, err = JOB.cache_file(f"{kind}.list", content, service_id=service, checksum=new_hash)
            if not cached:
                LOGGER.error(f"Error while caching blacklist : {err}")
                status = 2
                continue

            status = 1 if status != 2 else 2

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
    LOGGER.error(f"Exception while running blacklist-download.py :\n{e}")

sys_exit(status)
