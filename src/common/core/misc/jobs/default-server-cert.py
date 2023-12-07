#!/usr/bin/python3
# -*- coding: utf-8 -*-

from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("DEFAULT-SERVER-CERT", getenv("LOG_LEVEL", "INFO"))
JOB = Job(API(getenv("API_ADDR", ""), "job-default-server-cert"), getenv("CORE_TOKEN", None))
status = 0

try:
    # Check if we need to generate a self-signed default cert for non-SNI "clients"
    need_default_cert = False
    if getenv("MULTISITE", "yes") == "yes":
        for first_server in getenv("SERVER_NAME", "").split():
            for check_var in ("USE_CUSTOM_SSL", "AUTO_LETS_ENCRYPT", "GENERATE_SELF_SIGNED_SSL"):
                if getenv(f"{first_server}_{check_var}", getenv(check_var, "no")) == "yes":
                    need_default_cert = True
                    break
            if need_default_cert:
                break
    elif getenv("DISABLE_DEFAULT_SERVER", "no") == "yes" and ("yes" in (getenv("USE_CUSTOM_SSL", "no"), getenv("AUTO_LETS_ENCRYPT", "no"), getenv("GENERATE_SELF_SIGNED_SSL", "no"))):
        need_default_cert = True

    # Generate the self-signed certificate
    if not need_default_cert:
        LOGGER.info("Skipping generation of self-signed certificate for default server (not needed)")
        _exit(0)

    job_path = Path(sep, "var", "cache", "bunkerweb", "default-server-cert")
    job_path.mkdir(parents=True, exist_ok=True)

    cert_path = job_path.joinpath("cert.pem")
    if not cert_path.is_file():
        cached_pem = JOB.get_cache("cert.pem")

        if cached_pem:
            cert_path.write_bytes(cached_pem["data"])

    key_path = job_path.joinpath("cert.key")
    if not key_path.is_file():
        cached_key = JOB.get_cache("cert.key")

        if cached_key:
            key_path.write_bytes(cached_key["data"])

    if not cert_path.is_file():
        LOGGER.info("Generating self-signed certificate for default server")

        if (
            run(
                ["openssl", "req", "-nodes", "-x509", "-newkey", "rsa:4096", "-keyout", str(key_path), "-out", str(cert_path), "-days", "3650", "-subj", "/C=AU/ST=Some-State/O=Internet Widgits Pty Ltd/"],
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

        cached, err = JOB.cache_file("cert.pem", cert_path.read_bytes(), file_exists=True)
        if not cached:
            LOGGER.error(f"Error while saving default-server-cert cert.pem file to db cache : {err}")
        else:
            LOGGER.info("Successfully saved default-server-cert cert.pem file to db cache")

        cached, err = JOB.cache_file("cert.key", key_path.read_bytes(), file_exists=True)
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
