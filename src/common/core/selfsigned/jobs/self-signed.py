#!/usr/bin/env python3

from datetime import datetime, timedelta
from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Tuple

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("self-signed", getenv("LOG_LEVEL", "INFO"))
JOB = Job(LOGGER)
status = 0


def generate_cert(first_server: str, days: str, subj: str, self_signed_path: Path) -> Tuple[bool, int]:
    server_path = self_signed_path.joinpath(first_server)
    cert_path = server_path.joinpath("cert.pem")
    key_path = server_path.joinpath("key.pem")

    if cert_path.is_file() and key_path.is_file():
        if (
            run(
                ["openssl", "x509", "-checkend", "86400", "-noout", "-in", cert_path.as_posix()],
                stdin=DEVNULL,
                stderr=DEVNULL,
                check=False,
            ).returncode
            == 0
        ):
            LOGGER.info(f"Self-signed certificate already present for {first_server}")

            certificate = x509.load_pem_x509_certificate(JOB.get_cache("cert.pem", service_id=first_server), default_backend())
            if sorted(attribute.rfc4514_string() for attribute in certificate.subject) != sorted(v for v in subj.split("/") if v):
                LOGGER.warning(f"Subject of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ...")
            elif certificate.not_valid_after_utc - certificate.not_valid_before_utc != timedelta(days=int(days)):
                LOGGER.warning(
                    f"Expiration date of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ..."
                )
            elif certificate.not_valid_after_utc < datetime.now(tz=certificate.not_valid_after_utc.timetz().tzinfo):
                LOGGER.warning(f"Self-signed certificate for {first_server} has expired, regenerating ...")
            else:
                LOGGER.info(f"Self-signed certificate for {first_server} is valid")
                return True, 0

    LOGGER.info(f"Generating self-signed certificate for {first_server}")
    server_path.mkdir(parents=True, exist_ok=True)
    if (
        run(
            [
                "openssl",
                "req",
                "-nodes",
                "-x509",
                "-newkey",
                "ec",
                "-pkeyopt",
                "ec_paramgen_curve:prime256v1",
                "-keyout",
                key_path.as_posix(),
                "-out",
                cert_path.as_posix(),
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
        LOGGER.error(f"Self-signed certificate generation failed for {first_server}")
        return False, 2

    # Update db
    cached, err = JOB.cache_file("cert.pem", self_signed_path.joinpath(first_server, "cert.pem"), service_id=first_server, overwrite_file=False)
    if not cached:
        LOGGER.error(f"Error while caching self-signed cert.pem file for {first_server} : {err}")

    cached, err = JOB.cache_file("key.pem", self_signed_path.joinpath(first_server, "key.pem"), service_id=first_server, overwrite_file=False)
    if not cached:
        LOGGER.error(f"Error while caching self-signed {first_server}.key file : {err}")

    LOGGER.info(f"Successfully generated self-signed certificate for {first_server}")
    return True, 1


status = 0

try:
    self_signed_path = Path(sep, "var", "cache", "bunkerweb", "selfsigned")
    servers = getenv("SERVER_NAME") or []

    if isinstance(servers, str):
        servers = servers.split(" ")

    if not servers:
        LOGGER.info("No server found, skipping self-signed certificate generation ...")
        sys_exit(0)

    skipped_servers = []
    if getenv("MULTISITE", "no") == "no":
        servers = [servers[0]]
        if getenv("GENERATE_SELF_SIGNED_SSL", "no") == "no":
            LOGGER.info("Generate self-signed SSL is not enabled, skipping certificate generation ...")
            skipped_servers = servers

    if not skipped_servers:
        for first_server in servers:
            if getenv(f"{first_server}_GENERATE_SELF_SIGNED_SSL", getenv("GENERATE_SELF_SIGNED_SSL", "no")) != "yes":
                skipped_servers.append(first_server)
                continue

            LOGGER.info(f"Service {first_server} is using self-signed SSL certificates, checking ...")

            ret, ret_status = generate_cert(
                first_server,
                getenv(f"{first_server}_SELF_SIGNED_SSL_EXPIRY", getenv("SELF_SIGNED_SSL_EXPIRY", "365")),
                getenv(f"{first_server}_SELF_SIGNED_SSL_SUBJ", getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/")),
                self_signed_path,
            )
            if not ret:
                skipped_servers.append(first_server)
            status = ret_status

    for first_server in skipped_servers:
        JOB.del_cache("cert.pem", service_id=first_server)
        JOB.del_cache("key.pem", service_id=first_server)
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running self-signed.py :\n{format_exc()}")

sys_exit(status)
