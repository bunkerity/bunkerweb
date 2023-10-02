#!/usr/bin/python3

from datetime import timedelta
from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Tuple

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

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import set_file_in_db

logger = setup_logger("self-signed", getenv("LOG_LEVEL", "INFO"))
db = None
lock = Lock()
status = 0


def generate_cert(
    first_server: str, days: str, subj: str, self_signed_path: Path
) -> Tuple[bool, int]:
    if self_signed_path.joinpath(f"{first_server}.pem").is_file():
        if (
            run(
                [
                    "openssl",
                    "x509",
                    "-checkend",
                    "86400",
                    "-noout",
                    "-in",
                    str(self_signed_path.joinpath(f"{first_server}.pem")),
                ],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            ).returncode
            == 0
        ):
            logger.info(f"Self-signed certificate already present for {first_server}")

            certificate = x509.load_pem_x509_certificate(
                self_signed_path.joinpath(f"{first_server}.pem").read_bytes(),
                default_backend(),
            )
            if sorted(
                attribute.rfc4514_string() for attribute in certificate.subject
            ) != sorted(v for v in subj.split("/") if v):
                logger.warning(
                    f"Subject of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ..."
                )
            elif (
                certificate.not_valid_after - certificate.not_valid_before
                != timedelta(days=int(days))
            ):
                logger.warning(
                    f"Expiration date of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ..."
                )
            else:
                return True, 0

    logger.info(f"Generating self-signed certificate for {first_server}")
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
                str(self_signed_path.joinpath(f"{first_server}.key")),
                "-out",
                str(self_signed_path.joinpath(f"{first_server}.pem")),
                "-days",
                days,
                "-subj",
                subj,
            ],
            stdin=DEVNULL,
            stderr=DEVNULL,
            check=False,
        ).returncode
        != 0
    ):
        logger.error(f"Self-signed certificate generation failed for {first_server}")
        return False, 2

    # Update db
    cached, err = set_file_in_db(
        f"{first_server}.pem",
        self_signed_path.joinpath(f"{first_server}.pem").read_bytes(),
        db,
        service_id=first_server,
    )
    if not cached:
        logger.error(f"Error while caching self-signed {first_server}.pem file : {err}")

    cached, err = set_file_in_db(
        f"{first_server}.key",
        self_signed_path.joinpath(f"{first_server}.key").read_bytes(),
        db,
        service_id=first_server,
    )
    if not cached:
        logger.error(f"Error while caching self-signed {first_server}.key file : {err}")

    logger.info(f"Successfully generated self-signed certificate for {first_server}")
    return True, 1


status = 0

try:
    self_signed_path = Path(sep, "var", "cache", "bunkerweb", "selfsigned")
    self_signed_path.mkdir(parents=True, exist_ok=True)

    # Multisite case
    if getenv("MULTISITE") == "yes":
        servers = getenv("SERVER_NAME") or []

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if (
                not first_server
                or getenv(
                    f"{first_server}_GENERATE_SELF_SIGNED_SSL",
                    getenv("GENERATE_SELF_SIGNED_SSL", "no"),
                )
                != "yes"
                or self_signed_path.joinpath(f"{first_server}.pem").is_file()
            ):
                continue

            if not db:
                db = Database(
                    logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False
                )

            ret, ret_status = generate_cert(
                first_server,
                getenv(
                    f"{first_server}_SELF_SIGNED_SSL_EXPIRY",
                    getenv("SELF_SIGNED_SSL_EXPIRY", "365"),
                ),
                getenv(
                    f"{first_server}_SELF_SIGNED_SSL_SUBJ",
                    getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
                ),
                self_signed_path,
            )
            status = ret_status

    # Singlesite case
    elif getenv("GENERATE_SELF_SIGNED_SSL", "no") == "yes" and getenv("SERVER_NAME"):
        db = Database(
            logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False
        )

        first_server = getenv("SERVER_NAME", "").split(" ")[0]
        ret, ret_status = generate_cert(
            first_server,
            getenv("SELF_SIGNED_SSL_EXPIRY", "365"),
            getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
            self_signed_path,
        )
        status = ret_status
except:
    status = 2
    logger.error(f"Exception while running self-signed.py :\n{format_exc()}")

sys_exit(status)
