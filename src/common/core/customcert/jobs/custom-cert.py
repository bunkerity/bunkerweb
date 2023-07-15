#!/usr/bin/python3

from os import getenv, sep
from os.path import join, normpath
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from traceback import format_exc
from typing import Any, Dict, Optional

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
from jobs import cache_file, cache_hash, file_hash, send_cache_to_api

logger = setup_logger("CUSTOM-CERT", getenv("LOG_LEVEL", "INFO"))


def check_cert(
    cert_path: str,
    key_path: str,
    instance: str,
    base_path: Path,
    first_server: Optional[str] = None,
) -> bool:
    try:
        if not cert_path or not key_path:
            logger.warning(
                "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"
            )
            return False

        cert_path: Path = Path(normpath(cert_path))
        key_path: Path = Path(normpath(key_path))

        if not cert_path.is_file():
            logger.warning(
                f"Certificate file {cert_path} is not a valid file, ignoring the custom certificate"
            )
            return False
        elif not key_path.is_file():
            logger.warning(
                f"Key file {key_path} is not a valid file, ignoring the custom certificate"
            )
            return False

        cert_cache_path = base_path.joinpath(first_server or "", "cert.pem")
        cert_cache_path.parent.mkdir(parents=True, exist_ok=True)

        cert_hash = file_hash(cert_path)
        old_hash = cache_hash(cert_cache_path, instance, db)
        if old_hash == cert_hash:
            return False

        cached, err = cache_file(
            cert_path, cert_cache_path, cert_hash, instance, db, delete_file=False
        )
        if not cached:
            logger.error(f"Error while caching custom-cert cert.pem file : {err}")

        key_cache_path = base_path.joinpath(first_server or "", "key.pem")
        key_cache_path.parent.mkdir(parents=True, exist_ok=True)

        key_hash = file_hash(key_path)
        old_hash = cache_hash(key_cache_path, instance, db)
        if old_hash != key_hash:
            cached, err = cache_file(
                key_path, key_cache_path, key_hash, instance, db, delete_file=False
            )
            if not cached:
                logger.error(f"Error while caching custom-cert key.pem file : {err}")

        return True
    except:
        logger.error(
            f"Exception while running custom-cert.py (check_cert) :\n{format_exc()}",
        )
    return False


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
        instance_customcert_path = Path(
            sep,
            "var",
            "cache",
            "bunkerweb",
            "customcert",
            instance if instance != "127.0.0.1" else "",
        )
        instance_customcert_path.mkdir(parents=True, exist_ok=True)
        use_custom_cert = False

        if (
            config.get("USE_CUSTOM_SSL", "no") == "yes"
            and config.get("SERVER_NAME", "") != ""
        ):
            cert_path = config.get("CUSTOM_SSL_CERT", "")
            key_path = config.get("CUSTOM_SSL_KEY", "")

            if cert_path and key_path:
                logger.info(f"Checking certificate {cert_path} ...")
                need_reload = check_cert(
                    cert_path, key_path, instance, instance_customcert_path
                )
                if need_reload:
                    logger.info(f"Detected change for certificate {cert_path}")
                    use_custom_cert = True
                    status = 1
                else:
                    logger.info(f"No change for certificate {cert_path}")

        if config.get("MULTISITE", "no") == "yes":
            servers = config.get("SERVER_NAME") or []

            if isinstance(servers, str):
                servers = servers.split(" ")

            for first_server in servers:
                if not first_server or (
                    config.get(
                        f"{first_server}_USE_CUSTOM_SSL",
                        config.get("USE_CUSTOM_SSL", "no"),
                    )
                    != "yes"
                ):
                    continue

                cert_path = config.get(f"{first_server}_CUSTOM_SSL_CERT", "")
                key_path = config.get(f"{first_server}_CUSTOM_SSL_KEY", "")

                if cert_path and key_path:
                    logger.info(
                        f"Checking certificate {cert_path} ...",
                    )
                    need_reload = check_cert(
                        cert_path,
                        key_path,
                        instance,
                        instance_customcert_path,
                        first_server,
                    )
                    if need_reload:
                        logger.info(
                            f"Detected change for certificate {cert_path}",
                        )
                        use_custom_cert = True
                        status = 1
                    else:
                        logger.info(
                            f"No change for certificate {cert_path}",
                        )

        if instance != "127.0.0.1" and use_custom_cert:
            for api in apis:
                if f"{instance}:" in api.endpoint:
                    instance_api = api
                    break

            if not instance_api:
                logger.error(
                    f"Could not find an API for instance {instance}, configuration will not work as expected...",
                )
                continue

            sent, res = send_cache_to_api(instance_customcert_path, instance_api)
            if not sent:
                logger.error(f"Error while sending custom-cert data to API : {res}")
                status = 2
            logger.info(res)
except:
    status = 2
    logger.error(f"Exception while running custom-cert.py :\n{format_exc()}")

sys_exit(status)
