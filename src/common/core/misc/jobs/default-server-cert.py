#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)


from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("DEFAULT-SERVER-CERT", getenv("LOG_LEVEL", "INFO"))
JOB = Job()
status = 0

try:
    cert_path = Path(sep, "var", "cache", "bunkerweb", "default-server-cert")
    cert_path.mkdir(parents=True, exist_ok=True)
    if not cert_path.joinpath("cert.pem").is_file():
        LOGGER.info("Generating self-signed certificate for default server")

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
                    "/C=AU/ST=Some-State/O=Internet Widgits Pty Ltd/CN=www.example.org/",
                ],
                stdin=DEVNULL,
                stderr=DEVNULL,
                check=False,
            ).returncode
            != 0
        ):
            LOGGER.error("Self-signed certificate generation failed for default server")
            status = 2
        else:
            status = 1
            LOGGER.info("Successfully generated self-signed certificate for default server")

        cached, err = JOB.cache_file("cert.pem", cert_path.joinpath("cert.pem").read_bytes(), file_exists=True)
        if not cached:
            LOGGER.error(f"Error while saving default-server-cert cert.pem file to db cache : {err}")
        else:
            LOGGER.info("Successfully saved default-server-cert cert.pem file to db cache")

        cached, err = JOB.cache_file("cert.key", cert_path.joinpath("cert.key").read_bytes(), file_exists=True)
        if not cached:
            LOGGER.error(f"Error while saving default-server-cert cert.key file to db cache : {err}")
        else:
            LOGGER.info("Successfully saved default-server-cert cert.key file to db cache")
    else:
        LOGGER.info("Skipping generation of self-signed certificate for default server (already present)")
except:
    status = 2
    LOGGER.error(f"Exception while running default-server-cert.py :\n{format_exc()}")

sys_exit(status)
