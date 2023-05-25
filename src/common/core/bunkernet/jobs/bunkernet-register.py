#!/usr/bin/python3

from os import _exit, getenv
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from time import sleep
from traceback import format_exc

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/db",
        "/usr/share/bunkerweb/core/bunkernet/jobs",
    )
)

from bunkernet import register, ping, get_id
from Database import Database
from logger import setup_logger
from jobs import get_file_in_db, set_file_in_db, del_file_in_db

logger = setup_logger("BUNKERNET", getenv("LOG_LEVEL", "INFO"))
exit_status = 0

try:
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        servers = getenv("SERVER_NAME", [])

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if (
                getenv(f"{first_server}_USE_BUNKERNET", getenv("USE_BUNKERNET", "yes"))
                == "yes"
            ):
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True

    if not bunkernet_activated:
        logger.info("BunkerNet is not activated, skipping registration...")
        _exit(0)

    # Create directory if it doesn't exist
    Path("/var/cache/bunkerweb/bunkernet").mkdir(parents=True, exist_ok=True)

    # Get ID from cache
    bunkernet_id = None
    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    if db:
        bunkernet_id = get_file_in_db("instance.id", db)
        if bunkernet_id:
            Path("/var/cache/bunkerweb/bunkernet/instance.id").write_text(
                bunkernet_id.decode()
            )
            logger.info("Successfully retrieved BunkerNet ID from db cache")
        else:
            logger.info("No BunkerNet ID found in db cache")

    # Register instance
    registered = False
    if not Path("/var/cache/bunkerweb/bunkernet/instance.id").is_file():
        logger.info("Registering instance on BunkerNet API ...")
        ok, status, data = register()
        if not ok:
            logger.error(
                f"Error while sending register request to BunkerNet API : {data}"
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
                f"Received invalid data from BunkerNet API while sending db request : {data}, retrying later...",
            )
            _exit(2)

        if status != 200:
            logger.error(
                f"Error {status} from BunkerNet API : {data['data']}",
            )
            _exit(2)
        elif data.get("result", "ko") != "ok":
            logger.error(
                f"Received error from BunkerNet API while sending register request : {data.get('data', {})}"
            )
            _exit(2)
        bunkernet_id = data["data"]
        Path("/var/cache/bunkerweb/bunkernet/instance.id").write_text(bunkernet_id)
        registered = True
        exit_status = 1
        logger.info(
            f"Successfully registered on BunkerNet API with instance id {data['data']}"
        )
    else:
        bunkernet_id = Path("/var/cache/bunkerweb/bunkernet/instance.id").read_text()
        logger.info(f"Already registered on BunkerNet API with instance id {get_id()}")

    sleep(1)

    # Update cache with new bunkernet ID
    if db and registered:
        with open("/var/cache/bunkerweb/bunkernet/instance.id", "rb") as f:
            cached, err = set_file_in_db(f"instance.id", f, db)
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
            Path("/var/cache/bunkerweb/bunkernet/instance.id").unlink()
            if db:
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
