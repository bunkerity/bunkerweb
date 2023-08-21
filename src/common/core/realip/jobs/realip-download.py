#!/usr/bin/python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv, sep
from os.path import join, normpath
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
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
    realip_path = Path(sep, "var", "cache", "bunkerweb", "realip")
    realip_path.mkdir(parents=True, exist_ok=True)
    tmp_realip_path = Path(sep, "var", "tmp", "bunkerweb", "realip")
    tmp_realip_path.mkdir(parents=True, exist_ok=True)

    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)

    # Don't go further if the cache is fresh
    if is_cached_file(realip_path.joinpath("combined.list"), "hour", db):
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
            if url.startswith("file://"):
                with open(normpath(url[7:]), "rb") as f:
                    iterable = f.readlines()
            else:
                resp = get(url, stream=True, timeout=10)

                if resp.status_code != 200:
                    logger.warning(f"Got status code {resp.status_code}, skipping...")
                    continue

                iterable = resp.iter_lines()

            for line in iterable:
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

    tmp_realip_path.joinpath("combined.list").write_bytes(content)

    # Check if file has changed
    new_hash = file_hash(tmp_realip_path.joinpath("combined.list"))
    old_hash = cache_hash(realip_path.joinpath("combined.list"), db)
    if new_hash == old_hash:
        logger.info("New file is identical to cache file, reload is not needed")
        _exit(0)

    # Put file in cache
    cached, err = cache_file(
        tmp_realip_path.joinpath("combined.list"),
        realip_path.joinpath("combined.list"),
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
