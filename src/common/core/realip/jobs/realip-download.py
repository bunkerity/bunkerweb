#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv, sep
from os.path import join, normpath
from sys import exit as sys_exit, path as sys_path
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

from requests import get

from API import API  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import (
    bytes_hash,
    cache_file,
    cache_hash,
    del_cache,
    is_cached_file,
    update_cache_file_info,
)


def check_line(line):
    if "/" in line:
        with suppress(ValueError):
            ip_network(line)
            return True, line
    else:
        with suppress(ValueError):
            ip_address(line)
            return True, line
    return False, b""


LOGGER = setup_logger("REALIP", getenv("LOG_LEVEL", "INFO"))
CORE_API = API(getenv("API_ADDR", ""), "job-realip-download")
CORE_TOKEN = getenv("CORE_TOKEN", None)
status = 0

try:
    # Check if at least a server has Realip activated
    realip_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        servers = getenv("SERVER_NAME", [])

        if isinstance(servers, str):
            servers = servers.split()

        for first_server in servers:
            if getenv(f"{first_server}_USE_REAL_IP", getenv("USE_REAL_IP", "no")) == "yes":
                realip_activated = True
                break

    # Singlesite case
    elif getenv("USE_REAL_IP", "no") == "yes":
        realip_activated = True

    if not realip_activated:
        LOGGER.info("RealIP is not activated, skipping download...")
        _exit(0)

    # Get URLs
    urls = [url for url in getenv("REAL_IP_FROM_URLS", "").split(" ") if url]

    # Don't go further if the cache is fresh
    if is_cached_file("combined.list", "hour", CORE_API, CORE_TOKEN):
        LOGGER.info("RealIP list is already in cache, skipping download...")
        if not urls:
            LOGGER.warning("No URL found, deleting combined.list from cache...")
            deleted, err = del_cache("combined.list", CORE_API, CORE_TOKEN)
            if not deleted:
                LOGGER.warning(f"Couldn't delete combined.list from cache : {err}")
        _exit(0)

    # Download and write data to temp file
    i = 0
    content = b""
    for url in getenv("REAL_IP_FROM_URLS", "").split():
        if not url:
            continue

        try:
            LOGGER.info(f"Downloading RealIP list from {url} ...")
            if url.startswith("file://"):
                with open(normpath(url[7:]), "rb") as f:
                    iterable = f.readlines()
            else:
                resp = get(url, stream=True, timeout=10)

                if resp.status_code != 200:
                    LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                    continue

                iterable = resp.iter_lines()

            for line in iterable:
                line = line.strip().split(b" ")[0]

                if not line or line.startswith((b"#", b";")):
                    continue

                ok, data = check_line(line)
                if ok:
                    content += data + b"\n"
                    i += 1
        except:
            status = 2
            LOGGER.error(f"Exception while getting RealIP list from {url} :\n{format_exc()}")

    # Check if file has changed
    new_hash = bytes_hash(content)
    old_hash = cache_hash("combined.list", CORE_API, CORE_TOKEN)
    if new_hash == old_hash:
        LOGGER.info("New file is identical to cache file, reload is not needed")
        # Update file info in cache
        cached, err = update_cache_file_info("combined.list", CORE_API, CORE_TOKEN)
        if not cached:
            LOGGER.error(f"Error while updating cache info : {err}")
            _exit(2)
        _exit(0)

    # Put file in cache
    cached, err = cache_file(
        "combined.list",
        content,
        CORE_API,
        CORE_TOKEN,
        checksum=new_hash,
    )
    if not cached:
        LOGGER.error(f"Error while caching list : {err}")
        _exit(2)

    LOGGER.info(f"Downloaded {i} trusted IP/net")

    status = 1

except:
    status = 2
    LOGGER.error(f"Exception while running realip-download.py :\n{format_exc()}")

sys_exit(status)
