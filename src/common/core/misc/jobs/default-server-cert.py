#!/usr/bin/python3

from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Any, Dict

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("api",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import get_file_in_db, set_file_in_db, send_cache_to_api

logger = setup_logger("DEFAULT-SERVER-CERT", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )
    lock = Lock()
    with lock:
        configs: Dict[str, Dict[str, Any]] = db.get_config()
        bw_instances = db.get_instances()

    apis = []
    for instance in bw_instances:
        endpoint = f"http://{instance['hostname']}:{instance['port']}"
        host = instance["server_name"]
        apis.append(API(endpoint, host=host))

    for instance, config in configs.items():
        # Check if we need to generate a self-signed default cert for non-SNI "clients"
        need_default_cert = False
        if config.get("MULTISITE", "no") == "yes":
            for first_server in config.get("SERVER_NAME", "").split(" "):
                for check_var in (
                    "USE_CUSTOM_SSL",
                    "AUTO_LETS_ENCRYPT",
                    "GENERATE_SELF_SIGNED_SSL",
                ):
                    if (
                        config.get(
                            f"{first_server}_{check_var}", config.get(check_var, "no")
                        )
                        == "yes"
                    ):
                        need_default_cert = True
                        break
                if need_default_cert:
                    break
        elif config.get("DISABLE_DEFAULT_SERVER", "no") == "yes" and (
            "yes"
            in (
                config.get("USE_CUSTOM_SSL", "no"),
                config.get("AUTO_LETS_ENCRYPT", "no"),
                config.get("GENERATE_SELF_SIGNED_SSL", "no"),
            )
        ):
            need_default_cert = True

        # Generate the self-signed certificate
        if not need_default_cert:
            logger.info(
                "Skipping generation of self-signed certificate default server "
                + (f"for instance {instance}'s" if instance != "127.0.0.1" else "")
                + " (not needed)"
            )
            continue

        cert_path = Path(
            sep,
            "var",
            "cache",
            "bunkerweb",
            "default-server-cert",
            instance if instance != "127.0.0.1" else "",
        )
        cert_path.mkdir(parents=True, exist_ok=True)

        cert_file = get_file_in_db("cert.pem", instance, db)
        cert_file_path = cert_path.joinpath("cert.pem")
        if cert_file:
            cert_file_path.write_bytes(cert_file)
            logger.info(
                "Successfully retrieved default-server-cert cert.pem file from db cache"
            )
        else:
            logger.info("No default-server-cert cert.pem file found in db cache")

        key_file = get_file_in_db("cert.key", instance, db)
        key_file_path = cert_path.joinpath("cert.key")
        if key_file:
            key_file_path.write_bytes(key_file)
            logger.info(
                "Successfully retrieved default-server-cert cert.key file from db cache"
            )
        else:
            logger.info("No default-server-cert cert.key file found in db cache")

        if not cert_file_path.is_file() or not key_file_path.is_file():
            cert_file_path.unlink(missing_ok=True)
            key_file_path.unlink(missing_ok=True)
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
                        str(key_file_path),
                        "-out",
                        str(cert_file_path),
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

            cached, err = set_file_in_db(
                "cert.pem",
                cert_file_path.read_bytes(),
                instance,
                db,
            )
            if not cached:
                logger.error(
                    f"Error while saving default-server-cert cert.pem file to db cache : {err}"
                )
            else:
                logger.info(
                    "Successfully saved default-server-cert cert.pem file to db cache"
                )

            cached, err = set_file_in_db(
                "cert.key",
                key_file_path.read_bytes(),
                instance,
                db,
            )
            if not cached:
                logger.error(
                    f"Error while saving default-server-cert cert.key file to db cache : {err}"
                )
            else:
                logger.info(
                    "Successfully saved default-server-cert cert.key file to db cache"
                )

            if instance != "127.0.0.1":
                for api in apis:
                    if f"{instance}:" in api.endpoint:
                        instance_api = api
                        break

                if not instance_api:
                    logger.error(
                        f"Could not find an API for instance {instance}, configuration will not work as expected...",
                    )
                    continue

                sent, res = send_cache_to_api(cert_path, instance_api)
                if not sent:
                    logger.error(f"Error while sending default-server-cert data to API : {res}")
                    status = 2
                logger.info(res)
        else:
            logger.info(
                "Skipping generation of self-signed certificate for default server (already present)",
            )
except:
    status = 2
    logger.error(f"Exception while running default-server-cert.py :\n{format_exc()}")

sys_exit(status)
