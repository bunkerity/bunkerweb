#!/usr/bin/python3
# -*- coding: utf-8 -*-

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)


from logger import setup_logger  # type: ignore
from jobs import Job, file_hash  # type: ignore


LOGGER = setup_logger("CUSTOM-CERT", getenv("LOG_LEVEL", "INFO"))
JOB = Job()


def check_cert(cert_path: str, key_path: str, first_server: Optional[str] = None) -> bool:  # type: ignore
    try:
        if not cert_path or not key_path:
            LOGGER.warning("Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates")
            return False

        cert_path: Path = Path(cert_path)
        key_path: Path = Path(key_path)

        if not cert_path.is_file():
            LOGGER.warning(f"Certificate file {cert_path} is not a valid file, ignoring the custom certificate")
            return False
        elif not key_path.is_file():
            LOGGER.warning(f"Key file {key_path} is not a valid file, ignoring the custom certificate")
            return False

        cert_hash = file_hash(cert_path)
        old_hash = JOB.cache_hash("cert.pem", service_id=first_server)
        if old_hash == cert_hash:
            return False

        cached, err = JOB.cache_file("cert.pem", cert_path, service_id=first_server, checksum=cert_hash)
        if not cached:
            LOGGER.error(f"Error while caching custom-cert cert.pem file : {err}")

        key_hash = file_hash(key_path)
        old_hash = JOB.cache_hash("key.pem", service_id=first_server)
        if old_hash != key_hash:
            cached, err = JOB.cache_file("key.pem", key_path, service_id=first_server, checksum=key_hash)
            if not cached:
                LOGGER.error(f"Error while caching custom-cert key.pem file : {err}")

        return True
    except:
        LOGGER.error(
            f"Exception while running custom-cert.py (check_cert) :\n{format_exc()}",
        )
    return False


status = 0

try:
    if getenv("USE_CUSTOM_SSL", "no") == "yes" and getenv("SERVER_NAME", "") != "":
        cert_path = getenv("CUSTOM_SSL_CERT", "")
        key_path = getenv("CUSTOM_SSL_KEY", "")

        if cert_path and key_path:
            LOGGER.info(f"Checking certificate {cert_path} ...")
            need_reload = check_cert(cert_path, key_path)
            if need_reload:
                LOGGER.info(f"Detected change for certificate {cert_path}")
                status = 1
            else:
                LOGGER.info(f"No change for certificate {cert_path}")
        else:
            LOGGER.warning("Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates")

    if getenv("MULTISITE", "yes") == "yes":
        servers = getenv("SERVER_NAME") or []

        if isinstance(servers, str):
            servers = servers.split()

        for first_server in servers:
            if not first_server or (getenv(f"{first_server}_USE_CUSTOM_SSL", getenv("USE_CUSTOM_SSL", "no")) != "yes"):
                continue

            cert_path = getenv(f"{first_server}_CUSTOM_SSL_CERT", "")
            key_path = getenv(f"{first_server}_CUSTOM_SSL_KEY", "")

            if cert_path and key_path:
                LOGGER.info(
                    f"Checking certificate {cert_path} ...",
                )
                need_reload = check_cert(cert_path, key_path, first_server)
                if need_reload:
                    LOGGER.info(f"Detected change for certificate {cert_path}")
                    status = 1
                else:
                    LOGGER.info(f"No change for certificate {cert_path}")
            else:
                LOGGER.warning(f"Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates with service {first_server}")
except:
    status = 2
    LOGGER.error(f"Exception while running custom-cert.py :\n{format_exc()}")

sys_exit(status)
