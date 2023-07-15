#!/usr/bin/python3

from contextlib import suppress
from ipaddress import ip_address, ip_network
from os import _exit, getenv, sep
from os.path import join, normpath
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Any, Dict

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("api",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from API import API  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import cache_file, cache_hash, file_hash, is_cached_file, send_cache_to_api


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
    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    lock = Lock()
    with lock:
        configs: Dict[str, Dict[str, Any]] = db.get_config()
        bw_instances = db.get_instances()

    apis = []
    for instance in bw_instances:
        endpoint = f"http://{instance['hostname']}:{instance['port']}"
        host = instance["server_name"]
        apis.append(API(endpoint, host=host))

    # Check if at least a server has Realip activated
    realip_instances = []

    for instance, config in configs.items():
        # Multisite case
        if config.get("MULTISITE", "no") == "yes":
            servers = config.get("SERVER_NAME", [])

            if isinstance(servers, str):
                servers = servers.split(" ")

            for first_server in servers:
                if (
                    config.get(
                        f"{first_server}_USE_REAL_IP", config.get("USE_REAL_IP", "no")
                    )
                    == "yes"
                ):
                    realip_instances.append(instance)
                    break
        # Singlesite case
        elif config.get("USE_REAL_IP", "no") == "yes":
            realip_instances.append(instance)

    if not realip_instances:
        logger.info("RealIP is not activated, skipping download...")
        _exit(0)

    # Create directories if they don't exist
    realip_path = Path(sep, "var", "cache", "bunkerweb", "realip")
    tmp_realip_path = Path(sep, "var", "tmp", "bunkerweb", "realip")
    tmp_realip_path.mkdir(parents=True, exist_ok=True)
    instances_urls = {}

    for instance in realip_instances:
        # Get URLs
        urls = [
            url
            for url in configs[instance].get("REAL_IP_FROM_URLS", "").split(" ")
            if url
        ]

        same_as = None

        for instance_urls in instances_urls:
            if set(urls) == set(instances_urls[instance_urls]):
                same_as = instance_urls
                break

        instance_realip_path = realip_path.joinpath(
            same_as or (instance if instance != "127.0.0.1" else "")
        )
        instance_realip_path.mkdir(parents=True, exist_ok=True)

        combined_list_path = instance_realip_path.joinpath("combined.list")

        for api in apis:
            if f"{instance}:" in api.endpoint:
                instance_api = api
                break

        if not instance_api:
            logger.error(
                f"Could not find an API for instance {instance}, configuration will not work as expected...",
            )
            continue

        if same_as:
            if instance != "127.0.0.1":
                sent, res = send_cache_to_api(instance_realip_path, instance_api)
                if not sent:
                    logger.error(f"Error while sending realip data to API : {res}")
                    sys_exit(2)
                logger.info(res)
            continue

        instances_urls[instance] = urls

        # Don't go further if the cache is fresh
        if is_cached_file(combined_list_path, "hour", instance, db):
            logger.info("RealIP list is already in cache, skipping download...")
            continue

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
                        logger.warning(
                            f"Got status code {resp.status_code}, skipping..."
                        )
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

        tmp_combined_list_path = tmp_realip_path.joinpath("combined.list")
        tmp_combined_list_path.write_bytes(content)

        # Check if file has changed
        new_hash = file_hash(tmp_combined_list_path)
        old_hash = cache_hash(combined_list_path, instance, db)
        if new_hash == old_hash:
            logger.info("New file is identical to cache file, reload is not needed")
            _exit(0)

        # Put file in cache
        cached, err = cache_file(
            tmp_combined_list_path, combined_list_path, new_hash, instance, db
        )
        if not cached:
            logger.error(f"Error while caching list : {err}")
            _exit(2)

        logger.info(f"Downloaded {i} trusted IP/net")

        status = 1

        if instance != "127.0.0.1":
            sent, res = send_cache_to_api(instance_realip_path, instance_api)
            if not sent:
                logger.error(f"Error while sending realip data to API : {res}")
                status = 2
            logger.info(res)
except:
    status = 2
    logger.error(f"Exception while running realip-download.py :\n{format_exc()}")

sys_exit(status)
