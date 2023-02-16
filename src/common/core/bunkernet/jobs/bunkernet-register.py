#!/usr/bin/python3

from os import _exit, getenv, makedirs, remove
from os.path import isfile
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
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

logger = setup_logger("BUNKERNET", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
status = 0

try:

    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME").split(" "):
            if (
                getenv(f"{first_server}_USE_BUNKERNET", getenv("USE_BUNKERNET", "yes"))
                == "yes"
            ):
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True

    if bunkernet_activated is False:
        logger.info("BunkerNet is not activated, skipping registration...")
        _exit(0)

    # Create directory if it doesn't exist
    makedirs("/var/cache/bunkerweb/bunkernet", exist_ok=True)

    # Ask an ID if needed
    bunkernet_id = None
    if not isfile("/var/cache/bunkerweb/bunkernet/instance.id"):
        logger.info("Registering instance on BunkerNet API ...")
        ok, status, data = register()
        if not ok:
            logger.error(
                f"Error while sending register request to BunkerNet API : {data}"
            )
            _exit(1)
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
        elif status != 200:
            logger.error(
                f"Error {status} from BunkerNet API : {data['data']}",
            )
            _exit(1)
        elif data.get("result", "ko") != "ok":
            logger.error(
                f"Received error from BunkerNet API while sending register request : {data.get('data', {})}"
            )
            _exit(1)
        bunkernet_id = data["data"]
        logger.info(
            f"Successfully registered on BunkerNet API with instance id {data['data']}"
        )
    else:
        bunkernet_id = Path("/var/cache/bunkerweb/bunkernet/instance.id").read_text()
        logger.info(f"Already registered on BunkerNet API with instance id {get_id()}")

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
        elif status == 401:
            logger.warning(
                "Instance ID is not registered, removing it and retrying a register later...",
            )
            remove("/var/cache/bunkerweb/bunkernet/instance.id")
            _exit(2)
        elif data.get("result", "ko") != "ok":
            logger.error(
                f"Received error from BunkerNet API while sending ping request : {data.get('data', {})}, removing instance ID",
            )
            retry = True
        if not retry:
            bunkernet_ping = True
            break
        logger.warning("Waiting 1s and trying again ...")
        sleep(1)

    if bunkernet_ping and status != 403:
        logger.info("Connectivity with BunkerWeb is successful !")
        status = 1
        if not isfile("/var/cache/bunkerweb/bunkernet/instance.id"):
            Path("/var/cache/bunkerweb/bunkernet/instance.id").write_text(bunkernet_id)

            # Update db
            err = db.update_job_cache(
                "bunkernet-register",
                None,
                "instance.id",
                bunkernet_id.encode("utf-8"),
            )
            if err:
                logger.warning(f"Couldn't update db cache: {err}")
    else:
        logger.error("Connectivity with BunkerWeb failed ...")
        status = 2

except:
    status = 2
    logger.error(f"Exception while running bunkernet-register.py :\n{format_exc()}")

sys_exit(status)
