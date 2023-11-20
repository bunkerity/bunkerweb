#!/usr/bin/python3
# -*- coding: utf-8 -*-

from datetime import timedelta
from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Tuple

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("api",),
        ("utils",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from API import API  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("self-signed", getenv("LOG_LEVEL", "INFO"))
JOB = Job(API(getenv("API_ADDR", ""), "job-self-signed"), getenv("CORE_TOKEN", None))
status = 0


def generate_cert(first_server: str, days: str, subj: str, self_signed_path: Path, *, multisite: bool = False) -> Tuple[bool, int]:
    cert_path = self_signed_path.joinpath(first_server if multisite else "", "cert.pem")
    if not cert_path.is_file():
        cached_pem = JOB.get_cache("cert.pem", service_id=first_server)

        if cached_pem:
            cert_path.parent.mkdir(parents=True, exist_ok=True)
            cert_path.write_bytes(cached_pem["data"])

    key_path = self_signed_path.joinpath(first_server if multisite else "", "key.pem")
    if not key_path.is_file():
        cached_key = JOB.get_cache("key.pem", service_id=first_server)

        if cached_key:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(cached_key["data"])

    if cert_path.is_file():
        if (
            run(
                [
                    "openssl",
                    "x509",
                    "-checkend",
                    "86400",
                    "-noout",
                    "-in",
                    str(cert_path),
                ],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            ).returncode
            == 0
        ):
            LOGGER.info(f"Self-signed certificate already present for {first_server}")

            certificate = x509.load_pem_x509_certificate(cert_path.read_bytes(), default_backend())
            if sorted(attribute.rfc4514_string() for attribute in certificate.subject) != sorted(v for v in subj.split("/") if v):
                LOGGER.warning(f"Subject of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ...")
            elif certificate.not_valid_after - certificate.not_valid_before != timedelta(days=int(days)):
                LOGGER.warning(f"Expiration date of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ...")
            else:
                return True, 0

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info(f"Generating self-signed certificate for {first_server}")
    if (
        run(
            ["openssl", "req", "-nodes", "-x509", "-newkey", "rsa:4096", "-keyout", str(key_path), "-out", str(cert_path), "-days", days, "-subj", subj],
            stdin=DEVNULL,
            stderr=DEVNULL,
            check=False,
        ).returncode
        != 0
    ):
        LOGGER.error(f"Self-signed certificate generation failed for {first_server}")
        return False, 2

    # Update db
    cached, err = JOB.cache_file("cert.pem", cert_path.read_bytes(), service_id=first_server if multisite else None, file_exists=True)
    if not cached:
        LOGGER.error(f"Error while caching self-signed {first_server}.pem file : {err}")

    cached, err = JOB.cache_file("key.pem", key_path.read_bytes(), service_id=first_server if multisite else None, file_exists=True)
    if not cached:
        LOGGER.error(f"Error while caching self-signed {first_server}.key file : {err}")

    LOGGER.info(f"Successfully generated self-signed certificate for {first_server}")
    return True, 1


status = 0

try:
    self_signed_path = Path(sep, "var", "cache", "bunkerweb", "selfsigned")

    # Multisite case
    if getenv("MULTISITE") == "yes":
        servers = getenv("SERVER_NAME") or []

        if isinstance(servers, str):
            servers = servers.split()

        for first_server in servers:
            if (
                not first_server
                or getenv(
                    f"{first_server}_GENERATE_SELF_SIGNED_SSL",
                    getenv("GENERATE_SELF_SIGNED_SSL", "no"),
                )
                != "yes"
            ):
                continue

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
                multisite=True,
            )
            status = ret_status

    # Singlesite case
    elif getenv("GENERATE_SELF_SIGNED_SSL", "no") == "yes" and getenv("SERVER_NAME"):
        first_server = getenv("SERVER_NAME", "").split()[0]

        ret, ret_status = generate_cert(
            first_server,
            getenv("SELF_SIGNED_SSL_EXPIRY", "365"),
            getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
            self_signed_path,
        )
        status = ret_status
except:
    status = 2
    LOGGER.error(f"Exception while running self-signed.py :\n{format_exc()}")

sys_exit(status)
