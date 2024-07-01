#!/usr/bin/env python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import getenv, sep
from os.path import join, normpath
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
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
    if kind == "IP":
        if b"/" in line:
            with suppress(ValueError):
                ip_network(line.decode("utf-8"))
                return True, line
        else:
            with suppress(ValueError):
                ip_address(line.decode("utf-8"))
                return True, line
    elif kind == "RDNS":
        if rdns_rx.match(line):
            return True, line.lower()
    elif kind == "ASN":
        real_line = line.replace(b"AS", b"").replace(b"as", b"")
        if asn_rx.match(real_line):
            return True, real_line
    elif kind == "USER_AGENT":
        return True, b"(?:\\b)" + line + b"(?:\\b)"
    elif kind == "URI":
        if uri_rx.match(line):
            return True, line

    return False, b""


LOGGER = setup_logger("WHITELIST", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Check if at least a server has Whitelist activated
    whitelist_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if getenv(f"{first_server}_USE_WHITELIST", getenv("USE_WHITELIST", "yes")) == "yes":
                whitelist_activated = True
                break
    # Singlesite case
    elif getenv("USE_WHITELIST", "yes") == "yes":
        whitelist_activated = True

    if not whitelist_activated:
        LOGGER.info("Whitelist is not activated, skipping downloads...")
        sys_exit(0)

    JOB = Job(LOGGER)

    # Get URLs
    urls = {"IP": [], "RDNS": [], "ASN": [], "USER_AGENT": [], "URI": []}
    for kind in urls:
        for url in getenv(f"WHITELIST_{kind}_URLS", "").split(" "):
            if url and url not in urls[kind]:
                urls[kind].append(url)

    # Don't go further if the cache is fresh
    kinds_fresh = {"IP": True, "RDNS": True, "ASN": True, "USER_AGENT": True, "URI": True}
    for kind in kinds_fresh:
        if not JOB.is_cached_file(f"{kind}.list", "hour"):
            if urls[kind]:
                kinds_fresh[kind] = False
                LOGGER.info(f"Whitelist for {kind} is not cached, processing downloads..")
            continue

        LOGGER.info(f"Whitelist for {kind} is already in cache, skipping downloads...")

        if not urls[kind]:
            LOGGER.warning(f"Whitelist for {kind} is cached but no URL is configured, removing from cache...")
            deleted, err = JOB.del_cache(f"{kind}.list")
            if not deleted:
                LOGGER.warning(f"Couldn't delete {kind}.list from cache : {err}")

    if all(kinds_fresh.values()):
        if not any(urls.values()):
            LOGGER.info("No whitelist URL is configured, nothing to do...")
        sys_exit(0)

    # Loop on kinds
    for kind, urls_list in urls.items():
        if kinds_fresh[kind]:
            continue

        # Write combined data of the kind in memory and check if it has changed
        for url in urls_list:
            try:
                LOGGER.info(f"Downloading whitelist data from {url} ...")
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
                content = b""
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
                # Check if file has changed
                new_hash = bytes_hash(content)
                old_hash = JOB.cache_hash(f"{kind}.list")
                if new_hash == old_hash:
                    LOGGER.info(f"New file {kind}.list is identical to cache file, reload is not needed")
                else:
                    LOGGER.info(f"New file {kind}.list is different than cache file, reload is needed")
                    # Put file in cache
                    cached, err = JOB.cache_file(f"{kind}.list", content, checksum=new_hash)
                    if not cached:
                        LOGGER.error(f"Error while caching whitelist : {err}")
                        status = 2
                    else:
                        status = 1
            except:
                status = 2
                LOGGER.error(f"Exception while getting whitelist from {url} :\n{format_exc()}")
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running whitelist-download.py :\n{format_exc()}")

sys_exit(status)
