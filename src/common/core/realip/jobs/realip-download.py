#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from json import dumps, loads
from os import getenv, sep
from os.path import join, normpath
from pathlib import Path
from shutil import rmtree
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
        if b"/" in line:
            ip_network(line.decode())
            return True, line
        else:
            ip_address(line.decode())
            return True, line
    return False, b""


LOGGER = setup_logger("REALIP", getenv("LOG_LEVEL", "INFO"))
REALIP_CACHE_PATH = join(sep, "var", "cache", "bunkerweb", "realip")
status = 0

try:
    # Check if at least a server has Realip activated
    realip_activated = False

    # Check if at least a server has Greylist activated
    greylist_activated = False

    services = getenv("SERVER_NAME", "").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_realip_urls = {}

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_USE_REAL_IP", getenv("USE_REAL_IP", "no")) == "yes":
                realip_activated = True

                # Get URLs
                services_realip_urls[first_server] = set()
                for url in getenv(f"{first_server}_REAL_IP_FROM_URLS", getenv("REAL_IP_FROM_URLS", "")).strip().split(" "):
                    if url:
                        services_realip_urls[first_server].add(url)
    # Singlesite case
    elif getenv("USE_REAL_IP", "no") == "yes":
        realip_activated = True

        # Get URLs
        services_realip_urls[services[0]] = set()
        for url in getenv("REAL_IP_FROM_URLS", "").strip().split(" "):
            if url:
                services_realip_urls[services[0]].add(url)

    if not realip_activated:
        LOGGER.info("RealIP is not activated, skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER)

    if not any(services_realip_urls.values()):
        LOGGER.warning("No URL configured, nothing to do...")
        if Path(JOB.job_path.joinpath("urls.json")).exists():
            LOGGER.warning("RealIP URLs are cached but no URL is configured, removing from cache...")
            deleted, err = JOB.del_cache("urls.json")
            if not deleted:
                LOGGER.warning(f"Couldn't delete realip URLs from cache : {err}")
        sys_exit(0)

    cached_urls = loads(JOB.get_cache("urls.json") or "{}")

    tmp_downloads = Path(sep, "var", "tmp", "bunkerweb", "realip")
    tmp_downloads.mkdir(parents=True, exist_ok=True)
    downloaded_urls = {}
    failed_urls = set()
    current_timestamp = datetime.now().astimezone().timestamp()

    for service, urls in services_realip_urls.items():
        if not urls:
            if Path(JOB.job_path.joinpath(service, "combined.list")).exists():
                LOGGER.warning(f"{service} realip combined.list is cached but no URL is configured, removing from cache...")
                deleted, err = JOB.del_cache("combined.list", service_id=service)
                if not deleted:
                    LOGGER.warning(f"Couldn't delete {service} combined.list from cache : {err}")
            continue

        # Write combined data of the kind in memory and check if it has changed
        content = b""
        for url in urls:
            try:
                cached_url = cached_urls.get(url, {"time": 0, "tmp_path": ""})
                # Check if the URL's last download timestamp is younger than 1 hour
                if current_timestamp - cached_url["time"] < timedelta(hours=1).total_seconds():
                    downloaded_urls[url] = {
                        "time": cached_url["time"],
                        "tmp_path": tmp_downloads.joinpath(f"{bytes_hash(url, algorithm='sha1')}.list").as_posix(),
                    }
                    LOGGER.info(f"URL {url} has been downloaded less than 1 hour ago, skipping it...")
                    failed_urls.add(url)
                    status = 1 if status == 1 else 0
                    continue

                # Check if the URL has already been downloaded
                if url in failed_urls:
                    continue
                elif url in downloaded_urls:
                    LOGGER.info(f"URL {url} has already been downloaded, skipping it...")
                    content += Path(downloaded_urls[url]["tmp_path"]).read_bytes()
                else:
                    LOGGER.info(f"Downloading realip data from {url} ...")
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
                    for line in iterable:
                        line = line.strip().split(b" ")[0]

                        if not line or line.startswith((b"#", b";")):
                            continue

                        ok, data = check_line(line)
                        if ok:
                            content += data + b"\n"
                            i += 1

                    LOGGER.info(f"Downloaded {i} realip from {url}")
                    tmp_downloads.joinpath(f"{bytes_hash(url, algorithm='sha1')}.list").write_bytes(content)
                    downloaded_urls[url] = {
                        "time": current_timestamp,
                        "tmp_path": tmp_downloads.joinpath(f"{bytes_hash(url, algorithm='sha1')}.list").as_posix(),
                    }
            except BaseException as e:
                status = 2
                LOGGER.error(f"Exception while getting {service} realip from {url} :\n{e}")
                failed_urls.add(url)

        # Check if file has changed
        new_hash = bytes_hash(content)
        old_hash = JOB.cache_hash("combined.list", service_id=service)
        if new_hash == old_hash:
            LOGGER.info(f"New {service} file combined.list is identical to cache file, reload is not needed")
            continue

        LOGGER.info(f"New {service} file combined.list is different than cache file, reload is needed")
        # Put file in cache
        cached, err = JOB.cache_file("combined.list", content, service_id=service, checksum=new_hash)
        if not cached:
            LOGGER.error(f"Error while caching realip : {err}")
            status = 2
            continue

        status = 1

    cached, err = JOB.cache_file("urls.json", dumps(downloaded_urls, indent=2).encode("utf-8"))
    if not cached:
        LOGGER.error(f"Error while caching whitelist URLs : {err}")

    rmtree(tmp_downloads, ignore_errors=True)
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running realip-download.py :\n{format_exc()}")

sys_exit(status)
