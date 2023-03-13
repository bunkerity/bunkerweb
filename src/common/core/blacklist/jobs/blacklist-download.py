#!/usr/bin/python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv
from pathlib import Path
from re import IGNORECASE, compile as re_compile
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Tuple

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
from jobs import cache_file, cache_hash, is_cached_file, file_hash

rdns_rx = re_compile(rb"^(\.?[a-z\d\-]+)*\.[a-z]{2,}$", IGNORECASE)
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
        return True, line.replace(b"\\ ", b" ").replace(b"\\.", b"%.").replace(
            b"\\\\", b"\\"
        ).replace(b"-", b"%-")
    elif kind == "URI":
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

    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    lock = Lock()

    # Create directories if they don't exist
    Path("/var/cache/bunkerweb/blacklist").mkdir(parents=True, exist_ok=True)
    Path("/var/tmp/bunkerweb/blacklist").mkdir(parents=True, exist_ok=True)

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
        if not is_cached_file(f"/var/cache/bunkerweb/blacklist/{kind}.list", "hour"):
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
                resp = get(url, stream=True)

                if resp.status_code != 200:
                    continue

                i = 0
                content = b""
                for line in resp.iter_lines():
                    line = line.strip()

                    if not line or line.startswith(b"#") or line.startswith(b";"):
                        continue
                    elif kind != "USER_AGENT":
                        line = line.split(b" ")[0]

                    ok, data = check_line(kind, line)
                    if ok:
                        content += data + b"\n"
                        i += 1

                Path(f"/var/tmp/bunkerweb/blacklist/{kind}.list").write_bytes(content)

                logger.info(f"Downloaded {i} bad {kind}")
                # Check if file has changed
                new_hash = file_hash(f"/var/tmp/bunkerweb/blacklist/{kind}.list")
                old_hash = cache_hash(f"/var/cache/bunkerweb/blacklist/{kind}.list")
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
                        f"/var/tmp/bunkerweb/blacklist/{kind}.list",
                        f"/var/cache/bunkerweb/blacklist/{kind}.list",
                        new_hash,
                    )

                    if not cached:
                        logger.error(f"Error while caching blacklist : {err}")
                        status = 2
                    else:
                        # Update db
                        with lock:
                            err = db.update_job_cache(
                                "blacklist-download",
                                None,
                                f"{kind}.list",
                                content,
                                checksum=new_hash,
                            )

                        if err:
                            logger.warning(f"Couldn't update db cache: {err}")
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
