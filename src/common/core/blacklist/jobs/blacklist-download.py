#!/usr/bin/python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv, sep
from os.path import join, normpath
from pathlib import Path
from re import IGNORECASE, compile as re_compile
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Tuple

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("db",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import cache_file, cache_hash, is_cached_file, file_hash

rdns_rx = re_compile(rb"^[^ ]+$", IGNORECASE)
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


logger = setup_logger("BLACKLIST", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Check if at least a server has Blacklist activated
    blacklist_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if (
                getenv(f"{first_server}_USE_BLACKLIST", getenv("USE_BLACKLIST", "yes"))
                == "yes"
            ):
                blacklist_activated = True
                break
    # Singlesite case
    elif getenv("USE_BLACKLIST", "yes") == "yes":
        blacklist_activated = True

    if not blacklist_activated:
        logger.info("Blacklist is not activated, skipping downloads...")
        _exit(0)

    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)

    # Create directories if they don't exist
    blacklist_path = Path(sep, "var", "cache", "bunkerweb", "blacklist")
    blacklist_path.mkdir(parents=True, exist_ok=True)
    tmp_blacklist_path = Path(sep, "var", "tmp", "bunkerweb", "blacklist")
    tmp_blacklist_path.mkdir(parents=True, exist_ok=True)

    # Our urls data
    urls = {"IP": [], "RDNS": [], "ASN": [], "USER_AGENT": [], "URI": []}

    # Don't go further if the cache is fresh
    kinds_fresh = {
        "IP": True,
        "RDNS": True,
        "ASN": True,
        "USER_AGENT": True,
        "URI": True,
        "IGNORE_IP": True,
        "IGNORE_RDNS": True,
        "IGNORE_ASN": True,
        "IGNORE_USER_AGENT": True,
        "IGNORE_URI": True,
    }
    all_fresh = True
    for kind in kinds_fresh:
        if not is_cached_file(blacklist_path.joinpath(f"{kind}.list"), "hour", db):
            kinds_fresh[kind] = False
            all_fresh = False
            logger.info(
                f"Blacklist for {kind} is not cached, processing downloads..",
            )
        else:
            logger.info(
                f"Blacklist for {kind} is already in cache, skipping downloads...",
            )
    if all_fresh:
        _exit(0)

    # Get URLs
    urls = {
        "IP": [],
        "RDNS": [],
        "ASN": [],
        "USER_AGENT": [],
        "URI": [],
        "IGNORE_IP": [],
        "IGNORE_RDNS": [],
        "IGNORE_ASN": [],
        "IGNORE_USER_AGENT": [],
        "IGNORE_URI": [],
    }
    for kind in urls:
        for url in getenv(f"BLACKLIST_{kind}_URLS", "").split(" "):
            if url and url not in urls[kind]:
                urls[kind].append(url)

    # Loop on kinds
    for kind, urls_list in urls.items():
        if kinds_fresh[kind]:
            continue
        # Write combined data of the kind to a single temp file
        for url in urls_list:
            try:
                logger.info(f"Downloading blacklist data from {url} ...")
                if url.startswith("file://"):
                    with open(normpath(url[7:]), "rb") as f:
                        iterable = f.readlines()
                else:
                    resp = get(url, stream=True, timeout=10)

                    if resp.status_code != 200:
                        logger.warning(
                            f"Got status code {resp.status_code}, skipping..."
                        )
                        continue

                    iterable = resp.iter_lines()

                i = 0
                content = b""
                for line in iterable:
                    line = line.strip()

                    if not line or line.startswith(b"#") or line.startswith(b";"):
                        continue
                    elif kind != "USER_AGENT":
                        line = line.split(b" ")[0]

                    ok, data = check_line(kind, line)
                    if ok:
                        content += data + b"\n"
                        i += 1

                tmp_blacklist_path.joinpath(f"{kind}.list").write_bytes(content)

                logger.info(f"Downloaded {i} bad {kind}")
                # Check if file has changed
                new_hash = file_hash(tmp_blacklist_path.joinpath(f"{kind}.list"))
                old_hash = cache_hash(blacklist_path.joinpath(f"{kind}.list"), db)
                if new_hash == old_hash:
                    logger.info(
                        f"New file {kind}.list is identical to cache file, reload is not needed",
                    )
                else:
                    logger.info(
                        f"New file {kind}.list is different than cache file, reload is needed",
                    )
                    # Put file in cache
                    cached, err = cache_file(
                        tmp_blacklist_path.joinpath(f"{kind}.list"),
                        blacklist_path.joinpath(f"{kind}.list"),
                        new_hash,
                        db,
                    )

                    if not cached:
                        logger.error(f"Error while caching blacklist : {err}")
                        status = 2
                    else:
                        status = 1
            except:
                status = 2
                logger.error(
                    f"Exception while getting blacklist from {url} :\n{format_exc()}"
                )

except:
    status = 2
    logger.error(f"Exception while running blacklist-download.py :\n{format_exc()}")

sys_exit(status)
