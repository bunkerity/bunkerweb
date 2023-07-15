#!/usr/bin/python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Any, Dict, Tuple

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
from jobs import set_file_in_db, send_cache_to_api

logger = setup_logger("self-signed", getenv("LOG_LEVEL", "INFO"))
lock = Lock()
status = 0


def generate_cert(
    first_server: str, days: str, subj: str, self_signed_path: Path, instance: str
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
        instance,
        db,
        service_id=first_server,
    )
    if not cached:
        logger.error(f"Error while caching self-signed {first_server}.pem file : {err}")

    cached, err = set_file_in_db(
        f"{first_server}.key",
        self_signed_path.joinpath(f"{first_server}.key").read_bytes(),
        instance,
        db,
        service_id=first_server,
    )
    if not cached:
        logger.error(f"Error while caching self-signed {first_server}.key file : {err}")

    logger.info(f"Successfully generated self-signed certificate for {first_server}")
    return True, 1


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
        self_signed_path = Path(
            sep,
            "var",
            "cache",
            "bunkerweb",
            "selfsigned",
            instance if instance != "127.0.0.1" else "",
        )
        self_signed_path.mkdir(parents=True, exist_ok=True)
        use_self_signed = False

        # Multisite case
        if config.get("MULTISITE") == "yes":
            servers = config.get("SERVER_NAME") or []

            if isinstance(servers, str):
                servers = servers.split(" ")

            for first_server in servers:
                if (
                    not first_server
                    or config.get(
                        f"{first_server}_GENERATE_SELF_SIGNED_SSL",
                        config.get("GENERATE_SELF_SIGNED_SSL", "no"),
                    )
                    != "yes"
                    or self_signed_path.joinpath(f"{first_server}.pem").is_file()
                ):
                    continue

                if not db:
                    db = Database(
                        logger,
                        sqlalchemy_string=config.get("DATABASE_URI", None),
                    )

                use_self_signed, ret_status = generate_cert(
                    first_server,
                    config.get(
                        f"{first_server}_SELF_SIGNED_SSL_EXPIRY",
                        config.get("SELF_SIGNED_SSL_EXPIRY", "365"),
                    ),
                    config.get(
                        f"{first_server}_SELF_SIGNED_SSL_SUBJ",
                        config.get("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
                    ),
                    self_signed_path,
                    instance,
                )
                status = ret_status

        # Singlesite case
        elif config.get("GENERATE_SELF_SIGNED_SSL", "no") == "yes" and config.get(
            "SERVER_NAME"
        ):
            db = Database(
                logger,
                sqlalchemy_string=config.get("DATABASE_URI", None),
            )

            first_server = config.get("SERVER_NAME", "").split(" ")[0]
            use_self_signed, ret_status = generate_cert(
                first_server,
                config.get("SELF_SIGNED_SSL_EXPIRY", "365"),
                config.get("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
                self_signed_path,
                instance,
            )
            status = ret_status

        if instance != "127.0.0.1" and use_self_signed:
            for api in apis:
                if f"{instance}:" in api.endpoint:
                    instance_api = api
                    break

            if not instance_api:
                logger.error(
                    f"Could not find an API for instance {instance}, configuration will not work as expected...",
                )
                continue

            sent, res = send_cache_to_api(self_signed_path, instance_api)
            if not sent:
                logger.error(f"Error while sending selfsigned data to API : {res}")
                status = 2
            logger.info(res)
except:
    status = 2
    logger.error(f"Exception while running self-signed.py :\n{format_exc()}")

sys_exit(status)
