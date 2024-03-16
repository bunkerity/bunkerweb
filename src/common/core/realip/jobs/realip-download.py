#!/usr/bin/env python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join, normpath
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from logger import setup_logger  # type: ignore
from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore


def check_line(line):
    with suppress(ValueError):
        if "/" in line:
            ip_network(line)
            return True, line
        else:
            ip_address(line)
            return True, line
    return False, b""


LOGGER = setup_logger("REALIP", getenv("LOG_LEVEL", "INFO"))
REALIP_CACHE_PATH = join(sep, "var", "cache", "bunkerweb", "realip")
status = 0

try:
    # Check if at least a server has Realip activated
    realip_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        servers = getenv("SERVER_NAME", [])

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if getenv(f"{first_server}_USE_REAL_IP", getenv("USE_REAL_IP", "no")) == "yes":
                realip_activated = True
                break

    # Singlesite case
    elif getenv("USE_REAL_IP", "no") == "yes":
        realip_activated = True

    if not realip_activated:
        LOGGER.info("RealIP is not activated, skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER)

    # Get URLs
    urls = [url for url in getenv("REAL_IP_FROM_URLS", "").split(" ") if url]

    # Don't go further if the cache is fresh
    if JOB.is_cached_file("combined.list", "hour"):
        LOGGER.info("RealIP list is already in cache, skipping download...")
        if not urls:
            LOGGER.warning("No URL found, deleting combined.list from cache...")
            deleted, err = JOB.del_cache("combined.list")
            if not deleted:
                LOGGER.warning(f"Couldn't delete combined.list from cache : {err}")
        sys_exit(0)

    if not urls:
        LOGGER.info("No URL found, skipping download...")
        sys_exit(0)

    # Download and write data to temp file
    i = 0
    content = b""
    for url in urls:
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
    old_hash = JOB.cache_hash("combined.list")
    if new_hash == old_hash:
        LOGGER.info("New file is identical to cache file, reload is not needed")
        sys_exit(0)

    # Put file in cache
    cached, err = JOB.cache_file("combined.list", content, checksum=new_hash)
    if not cached:
        LOGGER.error(f"Error while caching list : {err}")
        sys_exit(2)

    LOGGER.info(f"Downloaded {i} trusted IP/net")

    status = 1
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running realip-download.py :\n{format_exc()}")

sys_exit(status)
