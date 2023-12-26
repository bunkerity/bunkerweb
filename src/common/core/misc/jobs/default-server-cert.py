#!/usr/bin/python3

from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

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
from jobs import set_file_in_db

logger = setup_logger("DEFAULT-SERVER-CERT", getenv("LOG_LEVEL", "INFO"))
status = 0

try:

    cert_path = Path(sep, "var", "cache", "bunkerweb", "default-server-cert")
    cert_path.mkdir(parents=True, exist_ok=True)
    if not cert_path.joinpath("cert.pem").is_file():
        logger.info("Generating self-signed certificate for default server")

        if (
            run(
                [
                    "openssl",
                    "req",
                    "-nodes",
                    "-x509",
                    "-newkey",
                    "rsa:4096",
                    "-keyout",
                    str(cert_path.joinpath("cert.key")),
                    "-out",
                    str(cert_path.joinpath("cert.pem")),
                    "-days",
                    "3650",
                    "-subj",
                    "/C=AU/ST=Some-State/O=Internet Widgits Pty Ltd/",
                ],
                stdin=DEVNULL,
                stderr=DEVNULL,
                check=False,
            ).returncode
            != 0
        ):
            logger.error(
                "Self-signed certificate generation failed for default server",
            )
            status = 2
        else:
            status = 1
            logger.info(
                "Successfully generated self-signed certificate for default server",
            )

        db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)

        cached, err = set_file_in_db(
            "cert.pem",
            cert_path.joinpath("cert.pem").read_bytes(),
            db,
        )
        if not cached:
            logger.error(f"Error while saving default-server-cert cert.pem file to db cache : {err}")
        else:
            logger.info("Successfully saved default-server-cert cert.pem file to db cache")

        cached, err = set_file_in_db(
            "cert.key",
            cert_path.joinpath("cert.key").read_bytes(),
            db,
        )
        if not cached:
            logger.error(f"Error while saving default-server-cert cert.key file to db cache : {err}")
        else:
            logger.info("Successfully saved default-server-cert cert.key file to db cache")
    else:
        logger.info(
            "Skipping generation of self-signed certificate for default server (already present)",
        )
except:
    status = 2
    logger.error(f"Exception while running default-server-cert.py :\n{format_exc()}")

sys_exit(status)
