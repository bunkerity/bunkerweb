#!/usr/bin/python3

from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from random import choice
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
        ("core", "bunkernet", "jobs"),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import data
from API import API  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import (
    cache_file,
    cache_hash,
    file_hash,
    is_cached_file,
    get_file_in_db,
    send_cache_to_api,
)

logger = setup_logger("BUNKERNET", getenv("LOG_LEVEL", "INFO"))
exit_status = 0

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

    # Check if at least a server has BunkerNet activated
    bunkernet_instances = []

    for instance, config in configs.items():
        # Multisite case
        configs[instance]["BUNKERNET_ACTIVATED"] = False
        if config.get("MULTISITE", "no") == "yes":
            servers = config.get("SERVER_NAME") or []

            if isinstance(servers, str):
                servers = servers.split(" ")

            for first_server in servers:
                if (
                    config.get(
                        f"{first_server}_USE_BUNKERNET",
                        config.get("USE_BUNKERNET", "yes"),
                    )
                    == "yes"
                ):
                    bunkernet_instances.append(instance)
                    break
        # Singlesite case
        elif config.get("USE_BUNKERNET", "yes") == "yes":
            bunkernet_instances.append(instance)

    if not bunkernet_instances:
        logger.info("BunkerNet is not activated, skipping download...")
        _exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)
    bunkernet_tmp_path = Path(sep, "var", "tmp", "bunkerweb", "bunkernet")
    bunkernet_tmp_path.mkdir(parents=True, exist_ok=True)

    instance = choice(bunkernet_instances)

    # Create empty file in case it doesn't exist
    ip_list_path = bunkernet_path.joinpath("ip.list")
    ip_list_path.touch(exist_ok=True)

    # Get ID from cache
    bunkernet_id = get_file_in_db("instance.id", instance, db)
    instance_id_path = bunkernet_path.joinpath(
        instance if instance != "127.0.0.1" else "", "instance.id"
    )
    if bunkernet_id:
        instance_id_path.write_bytes(bunkernet_id)
        logger.info("Successfully retrieved BunkerNet ID from db cache")
    else:
        logger.info("No BunkerNet ID found in db cache")

    # Check if ID is present
    if not instance_id_path.is_file():
        logger.error(
            "Not downloading BunkerNet data because instance is not registered",
        )
        _exit(2)

    # Don't go further if the cache is fresh
    if is_cached_file(ip_list_path, "day", None, db):
        logger.info(
            "BunkerNet list is already in cache, skipping download...",
        )
        _exit(0)

    exit_status = 1

    # Download data
    logger.info("Downloading BunkerNet data ...")
    ok, status, data = data()
    if not ok:
        logger.error(
            f"Error while sending data request to BunkerNet API : {data}",
        )
        _exit(2)
    elif status == 429:
        logger.warning(
            "BunkerNet API is rate limiting us, trying again later...",
        )
        _exit(0)
    elif status == 403:
        logger.warning(
            "BunkerNet has banned this instance, retrying a register later...",
        )
        _exit(0)

    try:
        assert isinstance(data, dict)
    except AssertionError:
        logger.error(
            f"Received invalid data from BunkerNet API while sending db request : {data}",
        )
        _exit(2)

    if data["result"] != "ok":
        logger.error(
            f"Received error from BunkerNet API while sending db request : {data['data']}, removing instance ID",
        )
        _exit(2)

    logger.info("Successfully downloaded data from BunkerNet API")

    # Writing data to file
    logger.info("Saving BunkerNet data ...")
    content = "\n".join(data["data"]).encode("utf-8")
    bunkernet_tmp_path.joinpath("ip.list").write_bytes(content)

    # Check if file has changed
    new_hash = file_hash(bunkernet_tmp_path.joinpath("ip.list"))
    old_hash = cache_hash(ip_list_path, instance, db)
    if new_hash == old_hash:
        logger.info(
            "New file is identical to cache file, reload is not needed",
        )
        _exit(0)

    # Put file in cache
    cached, err = cache_file(
        bunkernet_tmp_path.joinpath("ip.list"),
        ip_list_path,
        new_hash,
        None,
        db,
    )
    if not cached:
        logger.error(f"Error while caching BunkerNet data : {err}")
        _exit(2)

    logger.info("Successfully saved BunkerNet data")

    exit_status = 1

    for instance in bunkernet_instances:
        if instance != "127.0.0.1":
            for api in apis:
                if f"{instance}:" in api.endpoint:
                    instance_api = api
                    break

            if not instance_api:
                logger.error(
                    f"Could not find an API for instance {instance}, configuration will not work as expected...",
                )
                continue

            sent, res = send_cache_to_api(ip_list_path, instance_api)
            if not sent:
                logger.error(f"Error while sending bunkernet data to API : {res}")
                status = 2
            logger.info(res)
except:
    exit_status = 2
    logger.error(f"Exception while running bunkernet-data.py :\n{format_exc()}")

sys_exit(exit_status)
