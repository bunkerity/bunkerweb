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
        ("api",),
        ("utils",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import cache_file, get_cache

LOGGER = setup_logger("DEFAULT-SERVER-CERT", getenv("LOG_LEVEL", "INFO"))
CORE_API = API(getenv("API_ADDR", ""), "job-default-server-cert")
API_TOKEN = getenv("API_TOKEN", None)
status = 0

try:
    # Check if we need to generate a self-signed default cert for non-SNI "clients"
    need_default_cert = False
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            for check_var in (
                "USE_CUSTOM_SSL",
                "AUTO_LETS_ENCRYPT",
                "GENERATE_SELF_SIGNED_SSL",
            ):
                if (
                    getenv(f"{first_server}_{check_var}", getenv(check_var, "no"))
                    == "yes"
                ):
                    need_default_cert = True
                    break
            if need_default_cert:
                break
    elif getenv("DISABLE_DEFAULT_SERVER", "no") == "yes" and (
        "yes"
        in (
            getenv("USE_CUSTOM_SSL", "no"),
            getenv("AUTO_LETS_ENCRYPT", "no"),
            getenv("GENERATE_SELF_SIGNED_SSL", "no"),
        )
    ):
        need_default_cert = True

    # Generate the self-signed certificate
    if not need_default_cert:
        LOGGER.info(
            "Skipping generation of self-signed certificate for default server (not needed)",
        )
        _exit(0)

    cert_path = Path(sep, "var", "cache", "bunkerweb", "default-server-cert")
    cert_path.mkdir(parents=True, exist_ok=True)

    if not cert_path.joinpath("cert.pem").is_file():
        cached_pem = get_cache("cert.pem", CORE_API, API_TOKEN)

        if cached_pem:
            cert_path.joinpath("cert.pem").write_bytes(cached_pem["data"])

    if not cert_path.joinpath("cert.key").is_file():
        cached_key = get_cache("cert.key", CORE_API, API_TOKEN)

        if cached_key:
            cert_path.joinpath("cert.key").write_bytes(cached_key["data"])

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
                    "/C=AU/ST=Some-State/O=Internet Widgits Pty Ltd/",
                ],
                stdin=DEVNULL,
                stderr=DEVNULL,
                check=False,
            ).returncode
            != 0
        ):
            LOGGER.error(
                "Self-signed certificate generation failed for default server",
            )
            status = 2
        else:
            status = 1
            LOGGER.info(
                "Successfully generated self-signed certificate for default server",
            )

        cached, err = cache_file(
            "cert.pem",
            cert_path.joinpath("cert.pem").read_bytes(),
            CORE_API,
            API_TOKEN,
        )
        if not cached:
            LOGGER.error(
                f"Error while saving default-server-cert cert.pem file to db cache : {err}"
            )
        else:
            LOGGER.info(
                "Successfully saved default-server-cert cert.pem file to db cache"
            )

        cached, err = cache_file(
            "cert.key",
            cert_path.joinpath("cert.key").read_bytes(),
            CORE_API,
            API_TOKEN,
        )
        if not cached:
            LOGGER.error(
                f"Error while saving default-server-cert cert.key file to db cache : {err}"
            )
        else:
            LOGGER.info(
                "Successfully saved default-server-cert cert.key file to db cache"
            )
    else:
        LOGGER.info(
            "Skipping generation of self-signed certificate for default server (already present)",
        )
except:
    status = 2
    LOGGER.error(f"Exception while running default-server-cert.py :\n{format_exc()}")

sys_exit(status)
