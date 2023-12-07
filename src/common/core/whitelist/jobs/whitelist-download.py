#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv, sep
from os.path import join, normpath
from re import IGNORECASE, compile as re_compile
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Tuple

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from API import API  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import bytes_hash, Job  # type: ignore

rdns_rx = re_compile(rb"^[^ ]+$", IGNORECASE)
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
JOB = Job(API(getenv("API_ADDR", ""), "job-whitelist-download"), getenv("CORE_TOKEN", None))
status = 0

try:
    # Check if at least a server has Whitelist activated
    whitelist_activated = False
    # Multisite case
    if getenv("MULTISITE", "yes") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if getenv(f"{first_server}_USE_WHITELIST", getenv("USE_WHITELIST", "yes")) == "yes":
                whitelist_activated = True
                break
    # Singlesite case
    elif getenv("USE_WHITELIST", "yes") == "yes":
        whitelist_activated = True

    if not whitelist_activated:
        LOGGER.info("Whitelist is not activated, skipping downloads...")
        _exit(0)

    # Get URLs
    urls = {"IP": [], "RDNS": [], "ASN": [], "USER_AGENT": [], "URI": []}
    for kind in urls:
        for url in getenv(f"WHITELIST_{kind}_URLS", "").split(" "):
            if url and url not in urls[kind]:
                urls[kind].append(url)

    # Don't go further if the cache is fresh
    kinds_fresh = {"IP": True, "RDNS": True, "ASN": True, "USER_AGENT": True, "URI": True}
    all_fresh = True
    for kind in kinds_fresh:
        if not JOB.is_cached_file(f"{kind}.list", "hour")[1]:
            kinds_fresh[kind] = False
            all_fresh = False
            LOGGER.info(f"Whitelist for {kind} is not cached, processing downloads..")
        else:
            LOGGER.info(f"Whitelist for {kind} is already in cache, skipping downloads...")
            if not urls[kind]:
                LOGGER.warning(f"Whitelist for {kind} is cached but no URL is configured, removing from cache...")
                deleted, err = JOB.del_cache(f"{kind}.list")
                if not deleted:
                    LOGGER.warning(f"Couldn't delete {kind}.list from cache : {err}")
    if all_fresh:
        _exit(0)

    # Loop on kinds
    for kind, urls_list in urls.items():
        if kinds_fresh[kind]:
            continue
        # Write combined data of the kind to a single temp file
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
                    # Update file info in cache
                    cached, err = JOB.update_cache_file_info(f"{kind}.list")
                    if not cached:
                        LOGGER.error(f"Error while updating cache info : {err}")
                        _exit(2)
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

except:
    status = 2
    LOGGER.error(f"Exception while running whitelist-download.py :\n{format_exc()}")

sys_exit(status)
