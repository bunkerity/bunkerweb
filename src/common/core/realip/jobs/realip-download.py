#!/usr/bin/python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/db",
    )
)

from requests import get

from Database import Database
from logger import setup_logger
from jobs import cache_file, cache_hash, file_hash, is_cached_file


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


logger = setup_logger("REALIP", getenv("LOG_LEVEL", "INFO"))
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
            if (
                getenv(f"{first_server}_USE_REAL_IP", getenv("USE_REAL_IP", "no"))
                == "yes"
            ):
                realip_activated = True
                break

    # Singlesite case
    elif getenv("USE_REAL_IP", "no") == "yes":
        realip_activated = True

    if not realip_activated:
        logger.info("RealIP is not activated, skipping download...")
        _exit(0)

    # Create directories if they don't exist
    Path("/var/cache/bunkerweb/realip").mkdir(parents=True, exist_ok=True)
    Path("/var/tmp/bunkerweb/realip").mkdir(parents=True, exist_ok=True)

    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )

    # Don't go further if the cache is fresh
    if is_cached_file("/var/cache/bunkerweb/realip/combined.list", "hour", db):
        logger.info("RealIP list is already in cache, skipping download...")
        _exit(0)

    # Get URLs
    urls = [url for url in getenv("REAL_IP_FROM_URLS", "").split(" ") if url]

    # Download and write data to temp file
    i = 0
    content = b""
    for url in urls:
        try:
            logger.info(f"Downloading RealIP list from {url} ...")
            resp = get(url, stream=True)

            if resp.status_code != 200:
                continue

            for line in resp.iter_lines():
                line = line.strip().split(b" ")[0]

                if not line or line.startswith(b"#") or line.startswith(b";"):
                    continue

                ok, data = check_line(line)
                if ok:
                    content += data + b"\n"
                    i += 1
        except:
            status = 2
            logger.error(
                f"Exception while getting RealIP list from {url} :\n{format_exc()}"
            )

    Path("/var/tmp/bunkerweb/realip/combined.list").write_bytes(content)

    # Check if file has changed
    new_hash = file_hash("/var/tmp/bunkerweb/realip/combined.list")
    old_hash = cache_hash("/var/cache/bunkerweb/realip/combined.list", db)
    if new_hash == old_hash:
        logger.info("New file is identical to cache file, reload is not needed")
        _exit(0)

    # Put file in cache
    cached, err = cache_file(
        "/var/tmp/bunkerweb/realip-combined.list",
        "/var/cache/bunkerweb/realip/combined.list",
        new_hash,
        db,
    )
    if not cached:
        logger.error(f"Error while caching list : {err}")
        _exit(2)

    logger.info(f"Downloaded {i} trusted IP/net")

    status = 1

except:
    status = 2
    logger.error(f"Exception while running realip-download.py :\n{format_exc()}")

sys_exit(status)
