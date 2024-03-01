#!/usr/bin/env python3

from os import _exit, environ, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from tarfile import open as tar_open
from io import BytesIO
from shutil import rmtree

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import get_file_in_db, set_file_in_db  # type: ignore

logger = setup_logger("LETS-ENCRYPT.renew", getenv("LOG_LEVEL", "INFO"))
status = 0

LETS_ENCRYPT_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")

try:
    # Check if we're using let's encrypt
    use_letsencrypt = False
    if getenv("AUTO_LETS_ENCRYPT", "no") == "yes":
        use_letsencrypt = True
    elif getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True
                break

    if not use_letsencrypt:
        logger.info("Let's Encrypt is not activated, skipping renew...")
        _exit(0)

    # Create directory if it doesn't exist
    LETS_ENCRYPT_PATH.mkdir(parents=True, exist_ok=True)
    Path(sep, "var", "lib", "bunkerweb", "letsencrypt").mkdir(parents=True, exist_ok=True)

    # Extract letsencrypt folder if it exists in db
    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"), pool=False)

    tgz = get_file_in_db("folder.tgz", db)
    if tgz:
        # Delete folder if needed
        if LETS_ENCRYPT_PATH.exists():
            rmtree(LETS_ENCRYPT_PATH, ignore_errors=True)
        LETS_ENCRYPT_PATH.mkdir(parents=True, exist_ok=True)
        # Extract it
        with tar_open(name="folder.tgz", mode="r:gz", fileobj=BytesIO(tgz)) as tf:
            tf.extractall(LETS_ENCRYPT_PATH)
        logger.info("Successfully retrieved Let's Encrypt data from db cache")
    else:
        logger.info("No Let's Encrypt data found in db cache")

    if (
        run(
            [
                join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot"),
                "renew",
                "--no-random-sleep-on-renew",
                "--config-dir",
                LETS_ENCRYPT_PATH.joinpath("etc").as_posix(),
                "--work-dir",
                join(sep, "var", "lib", "bunkerweb", "letsencrypt"),
                "--logs-dir",
                join(sep, "var", "log", "bunkerweb"),
            ],
            stdin=DEVNULL,
            stderr=STDOUT,
            env=environ.copy() | {"PYTHONPATH": join(sep, "usr", "share", "bunkerweb", "deps", "python")},
            check=False,
        ).returncode
        != 0
    ):
        status = 2
        logger.error("Certificates renewal failed")

    # Put new folder in cache
    bio = BytesIO()
    with tar_open("folder.tgz", mode="w:gz", fileobj=bio, compresslevel=9) as tgz:
        tgz.add(LETS_ENCRYPT_PATH, arcname=".")
    bio.seek(0, 0)

    # Put tgz in cache
    cached, err = set_file_in_db("folder.tgz", bio.read(), db)
    if not cached:
        logger.error(f"Error while saving Let's Encrypt data to db cache : {err}")
    else:
        logger.info("Successfully saved Let's Encrypt data to db cache")
except:
    status = 2
    logger.error(f"Exception while running certbot-renew.py :\n{format_exc()}")

sys_exit(status)
