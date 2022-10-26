#!/usr/bin/python3

from ipaddress import ip_address, ip_network
from os import _exit, getenv, makedirs
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/db")

from requests import get

from Database import Database
from logger import setup_logger
from jobs import cache_file, cache_hash, file_hash, is_cached_file


def check_line(line):
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


logger = setup_logger("REALIP", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
    bw_integration="Kubernetes"
    if getenv("KUBERNETES_MODE", "no") == "yes"
    else "Cluster",
)
status = 0

try:

    # Check if at least a server has Blacklist activated
    blacklist_activated = False
    # Multisite case
    if getenv("MULTISITE") == "yes":
        for first_server in getenv("SERVER_NAME").split(" "):
            if getenv(first_server + "_USE_REAL_IP", getenv("USE_REAL_IP")) == "yes":
                blacklist_activated = True
                break
    # Singlesite case
    elif getenv("USE_REAL_IP") == "yes":
        blacklist_activated = True
    if not blacklist_activated:
        logger.info("RealIP is not activated, skipping download...")
        _exit(0)

    # Create directory if it doesn't exist
    makedirs("/opt/bunkerweb/cache/realip", exist_ok=True)

    # Don't go further if the cache is fresh
    if is_cached_file("/opt/bunkerweb/cache/realip/combined.list", "hour"):
        logger.info("RealIP list is already in cache, skipping download...")
        _exit(0)

    # Get URLs
    urls = []
    for url in getenv("REALIP_FROM_URLS", "").split(" "):
        if url != "" and url not in urls:
            urls.append(url)

    # Download and write data to temp file
    i = 0
    content = ""
    for url in urls:
        try:
            logger.info(f"Downloading RealIP list from {url} ...")
            resp = get(url, stream=True)
            if resp.status_code != 200:
                continue
            for line in resp.iter_lines(decode_unicode=True):
                line = line.strip().split(" ")[0]
                if line == "" or line.startswith("#") or line.startswith(";"):
                    continue
                ok, data = check_line(line)
                if ok:
                    content += f"{data}\n"
                    i += 1
        except:
            status = 2
            logger.error(
                f"Exception while getting RealIP list from {url} :\n{format_exc()}"
            )

    with open("/opt/bunkerweb/tmp/realip-combined.list", "w") as f:
        f.write(content)

    # Check if file has changed
    new_hash = file_hash("/opt/bunkerweb/tmp/realip-combined.list")
    old_hash = cache_hash("/opt/bunkerweb/cache/realip/combined.list")
    if new_hash == old_hash:
        logger.info("New file is identical to cache file, reload is not needed")
        _exit(0)

    # Put file in cache
    cached, err = cache_file(
        "/opt/bunkerweb/tmp/realip-combined.list",
        "/opt/bunkerweb/cache/realip/combined.list",
        new_hash,
    )
    if not cached:
        logger.error(f"Error while caching list : {err}")
        _exit(2)

    # Update db
    err = db.update_job_cache(
        "realip-download",
        None,
        "combined.list",
        content.encode("utf-8"),
        checksum=new_hash,
    )
    if err:
        logger.warning(f"Couldn't update db cache: {err}")

    logger.info(f"Downloaded {i} trusted IP/net")

    status = 1

except:
    status = 2
    logger.error(f"Exception while running realip-download.py :\n{format_exc()}")

sys_exit(status)
