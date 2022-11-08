#!/usr/bin/python3

from ipaddress import ip_address, ip_network
from os import _exit, getenv, makedirs
from re import match
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/db")

from requests import get

from Database import Database
from logger import setup_logger
from jobs import cache_file, cache_hash, is_cached_file, file_hash


def check_line(kind, line):
    if kind == "IP":
        if "/" in line:
            try:
                ip_network(line)
                return True, line
            except ValueError:
                pass
        else:
            try:
                ip_address(line)
                return True, line
            except ValueError:
                pass
        return False, ""
    elif kind == "RDNS":
        if match(r"^(\.?[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$", line):
            return True, line.lower()
        return False, ""
    elif kind == "ASN":
        real_line = line.replace("AS", "")
        if match(r"^\d+$", real_line):
            return True, real_line
    elif kind == "USER_AGENT":
        return True, line.replace("\\ ", " ").replace("\\.", "%.").replace(
            "\\\\", "\\"
        ).replace("-", "%-")
    elif kind == "URI":
        if match(r"^/", line):
            return True, line
    return False, ""


logger = setup_logger("GREYLIST", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
status = 0

try:

    # Check if at least a server has Greylist activated
    greylist_activated = False
    # Multisite case
    if getenv("MULTISITE") == "yes":
        for first_server in getenv("SERVER_NAME").split(" "):
            if getenv(first_server + "_USE_GREYLIST", getenv("USE_GREYLIST")) == "yes":
                greylist_activated = True
                break
    # Singlesite case
    elif getenv("USE_GREYLIST") == "yes":
        greylist_activated = True
    if not greylist_activated:
        logger.info("Greylist is not activated, skipping downloads...")
        _exit(0)

    # Create directories if they don't exist
    makedirs("/opt/bunkerweb/cache/greylist", exist_ok=True)
    makedirs("/opt/bunkerweb/tmp/greylist", exist_ok=True)

    # Our urls data
    urls = {"IP": [], "RDNS": [], "ASN": [], "USER_AGENT": [], "URI": []}

    # Don't go further if the cache is fresh
    kinds_fresh = {
        "IP": True,
        "RDNS": True,
        "ASN": True,
        "USER_AGENT": True,
        "URI": True,
    }
    all_fresh = True
    for kind in kinds_fresh:
        if not is_cached_file(f"/opt/bunkerweb/cache/greylist/{kind}.list", "hour"):
            kinds_fresh[kind] = False
            all_fresh = False
            logger.info(
                f"Greylist for {kind} is not cached, processing downloads..",
            )
        else:
            logger.info(
                f"Greylist for {kind} is already in cache, skipping downloads...",
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
    }
    for kind in urls:
        for url in getenv(f"GREYLIST_{kind}_URLS", "").split(" "):
            if url != "" and url not in urls[kind]:
                urls[kind].append(url)

    # Loop on kinds
    for kind, urls_list in urls.items():
        if kinds_fresh[kind]:
            continue
        # Write combined data of the kind to a single temp file
        for url in urls_list:
            try:
                logger.info(f"Downloading greylist data from {url} ...")
                resp = get(url)
                if resp.status_code != 200:
                    continue
                i = 0
                with open(f"/opt/bunkerweb/tmp/greylist/{kind}.list", "w") as f:
                    for line in resp.content.decode("utf-8").splitlines():
                        line = line.strip()
                        if kind != "USER_AGENT":
                            line = line.strip().split(" ")[0]
                        if line == "" or line.startswith("#") or line.startswith(";"):
                            continue
                        ok, data = check_line(kind, line)
                        if ok:
                            f.write(data + "\n")
                            i += 1
                logger.info(f"Downloaded {i} bad {kind}")
                # Check if file has changed
                new_hash = file_hash(f"/opt/bunkerweb/tmp/greylist/{kind}.list")
                old_hash = cache_hash(f"/opt/bunkerweb/cache/greylist/{kind}.list")
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
                        f"/opt/bunkerweb/tmp/greylist/{kind}.list",
                        f"/opt/bunkerweb/cache/greylist/{kind}.list",
                        new_hash,
                    )
                    if not cached:
                        logger.error(f"Error while caching greylist : {err}")
                        status = 2
                    if status != 2:
                        # Update db
                        err = db.update_job_cache(
                            "greylist-download",
                            None,
                            f"{kind}.list",
                            resp.content,
                            checksum=new_hash,
                        )
                        if err:
                            logger.warning(f"Couldn't update db cache: {err}")
                        status = 1
            except:
                status = 2
                logger.error(
                    f"Exception while getting greylist from {url} :\n{format_exc()}"
                )

except:
    status = 2
    logger.error(f"Exception while running greylist-download.py :\n{format_exc()}")

sys_exit(status)
