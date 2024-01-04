#!/usr/bin/python3

from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("db",),
        ("core", "bunkernet", "jobs"),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import register, ping
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import get_file_in_db, set_file_in_db, del_file_in_db  # type: ignore

logger = setup_logger("BUNKERNET", getenv("LOG_LEVEL", "INFO"))
exit_status = 0

try:
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        servers = getenv("SERVER_NAME") or []

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if getenv(f"{first_server}_USE_BUNKERNET", getenv("USE_BUNKERNET", "yes")) == "yes":
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True

    if not bunkernet_activated:
        logger.info("BunkerNet is not activated, skipping registration...")
        _exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)

    # Get ID from cache
    bunkernet_id = None
    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)
    bunkernet_id = get_file_in_db("instance.id", db)
    if bunkernet_id:
        bunkernet_path.joinpath("instance.id").write_bytes(bunkernet_id)
        logger.info("Successfully retrieved BunkerNet ID from db cache")
    else:
        logger.info("No BunkerNet ID found in db cache")

    # Register instance
    registered = False
    instance_id_path = bunkernet_path.joinpath("instance.id")
    if not instance_id_path.is_file():
        logger.info("Registering instance on BunkerNet API ...")
        ok, status, data = register()
        if not ok:
            logger.error(f"Error while sending register request to BunkerNet API : {data}")
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
                f"Received invalid data from BunkerNet API while sending db request : {data}, retrying later...",
            )
            _exit(2)

        if status != 200:
            logger.error(
                f"Error {status} from BunkerNet API : {data['data']}",
            )
            _exit(2)
        elif data.get("result", "ko") != "ok":
            logger.error(f"Received error from BunkerNet API while sending register request : {data.get('data', {})}")
            _exit(2)
        bunkernet_id = data["data"]
        instance_id_path.write_text(bunkernet_id, encoding="utf-8")
        registered = True
        exit_status = 1
        logger.info(f"Successfully registered on BunkerNet API with instance id {data['data']}")
    else:
        bunkernet_id = bunkernet_id or instance_id_path.read_bytes()
        bunkernet_id = bunkernet_id.decode()
        logger.info(f"Already registered on BunkerNet API with instance id {bunkernet_id}")

    sleep(1)

    # Update cache with new bunkernet ID
    if registered:
        cached, err = set_file_in_db("instance.id", bunkernet_id.encode(), db)
        if not cached:
            logger.error(f"Error while saving BunkerNet data to db cache : {err}")
        else:
            logger.info("Successfully saved BunkerNet data to db cache")

    # Ping
    logger.info("Checking connectivity with BunkerNet API ...")
    bunkernet_ping = False
    for i in range(0, 5):
        ok, status, data = ping(bunkernet_id)
        retry = False
        if not ok:
            logger.error(f"Error while sending ping request to BunkerNet API : {data}")
            retry = True
        elif status == 429:
            logger.warning(
                "BunkerNet API is rate limiting us, trying again later...",
            )
            retry = True
        elif status == 403:
            logger.warning(
                "BunkerNet has banned this instance, retrying a register later...",
            )
            _exit(2)
        elif status == 401:
            logger.warning(
                "Instance ID is not registered, removing it and retrying a register later...",
            )
            instance_id_path.unlink()
            del_file_in_db("instance.id", db)
            _exit(2)

        try:
            assert isinstance(data, dict)
        except AssertionError:
            logger.error(
                f"Received invalid data from BunkerNet API while sending db request : {data}, retrying later...",
            )
            _exit(2)

        if data.get("result", "ko") != "ok":
            logger.error(
                f"Received error from BunkerNet API while sending ping request : {data.get('data', {})}",
            )
            retry = True
        if not retry:
            bunkernet_ping = True
            break
        logger.warning("Waiting 1s and trying again ...")
        sleep(1)

    if bunkernet_ping:
        logger.info("Connectivity with BunkerNet is successful !")
    else:
        logger.error("Connectivity with BunkerNet failed ...")
        exit_status = 2
except:
    exit_status = 2
    logger.error(f"Exception while running bunkernet-register.py :\n{format_exc()}")

sys_exit(exit_status)
