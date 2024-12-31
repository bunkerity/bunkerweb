#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from typing import Tuple, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("CUSTOM-CERT", getenv("LOG_LEVEL", "INFO"))
JOB = Job(LOGGER, __file__)


def check_cert(cert_file: Union[Path, bytes], key_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    try:
        ret = False
        if not cert_file or not key_file:
            return False, "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"

        if isinstance(cert_file, Path):
            if not cert_file.is_file():
                return False, f"Certificate file {cert_file} is not a valid file, ignoring the custom certificate"
            cert_file = cert_file.read_bytes()

        if isinstance(key_file, Path):
            if not key_file.is_file():
                return False, f"Key file {key_file} is not a valid file, ignoring the custom certificate"
            key_file = key_file.read_bytes()

        cert_hash = bytes_hash(cert_file)
        old_hash = JOB.cache_hash("cert.pem", service_id=first_server)
        if old_hash != cert_hash:
            ret = True
            cached, err = JOB.cache_file("cert.pem", cert_file, service_id=first_server, checksum=cert_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-cert cert.pem file : {err}")
                return False, err

        key_hash = bytes_hash(key_file)
        old_hash = JOB.cache_hash("key.pem", service_id=first_server)
        if old_hash != key_hash:
            ret = True
            cached, err = JOB.cache_file("key.pem", key_file, service_id=first_server, checksum=key_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-key key.pem file : {err}")
                return False, err

        return ret, ""
    except BaseException as e:
        return False, e


status = 0

try:
    all_domains = getenv("SERVER_NAME") or []

    if isinstance(all_domains, str):
        all_domains = all_domains.split(" ")

    if not all_domains:
        LOGGER.info("No services found, exiting ...")
        sys_exit(0)

    skipped_servers = []
    if not getenv("MULTISITE", "no") == "yes":
        all_domains = [all_domains[0]]
        if getenv("USE_CUSTOM_SSL", "no") == "no":
            LOGGER.info("Custom SSL is not enabled, skipping ...")
            skipped_servers = all_domains

    if not skipped_servers:
        for first_server in all_domains:
            if getenv(f"{first_server}_USE_CUSTOM_SSL", getenv("USE_CUSTOM_SSL", "no")) == "no":
                skipped_servers.append(first_server)
                continue

            LOGGER.info(f"Service {first_server} is using custom SSL certificates, checking ...")

            cert_priority = getenv(f"{first_server}_CUSTOM_SSL_CERT_PRIORITY", getenv("CUSTOM_SSL_CERT_PRIORITY", "file"))
            cert_file = getenv(f"{first_server}_CUSTOM_SSL_CERT", getenv("CUSTOM_SSL_CERT", ""))
            key_file = getenv(f"{first_server}_CUSTOM_SSL_KEY", getenv("CUSTOM_SSL_KEY", ""))
            cert_data = getenv(f"{first_server}_CUSTOM_SSL_CERT_DATA", getenv("CUSTOM_SSL_CERT_DATA", ""))
            key_data = getenv(f"{first_server}_CUSTOM_SSL_KEY_DATA", getenv("CUSTOM_SSL_KEY_DATA", ""))

            if (cert_file or cert_data) and (key_file or key_data):
                if (cert_priority == "file" or not cert_data) and cert_file:
                    cert_file = Path(cert_file)
                else:
                    try:
                        cert_file = b64decode(cert_data)
                    except BaseException:
                        LOGGER.exception(f"Error while decoding cert data, skipping server {first_server}...")
                        skipped_servers.append(first_server)
                        status = 2
                        continue

                if (cert_priority == "file" or not key_data) and key_file:
                    key_file = Path(key_file)
                else:
                    try:
                        key_file = b64decode(key_data)
                    except BaseException:
                        LOGGER.exception(f"Error while decoding key data, skipping server {first_server}...")
                        skipped_servers.append(first_server)
                        status = 2
                        continue

                LOGGER.info(f"Checking certificate for {first_server} ...")
                need_reload, err = check_cert(cert_file, key_file, first_server)
                if isinstance(err, BaseException):
                    LOGGER.error(f"Exception while checking {first_server}'s certificate, skipping ... \n{err}")
                    skipped_servers.append(first_server)
                    status = 2
                    continue
                elif err:
                    LOGGER.warning(f"Error while checking {first_server}'s certificate : {err}")
                    skipped_servers.append(first_server)
                    status = 2
                    continue
                elif need_reload:
                    LOGGER.info(f"Detected change in {first_server}'s certificate")
                    status = 1
                    continue

                LOGGER.info(f"No change in {first_server}'s certificate")
            elif not cert_file or not key_file:
                LOGGER.warning(
                    "Variables (CUSTOM_SSL_CERT or CUSTOM_SSL_CERT_DATA) and (CUSTOM_SSL_KEY or CUSTOM_SSL_KEY_DATA) have to be set to use custom certificates"
                )
                skipped_servers.append(first_server)

    for first_server in skipped_servers:
        JOB.del_cache("cert.pem", service_id=first_server)
        JOB.del_cache("key.pem", service_id=first_server)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.error(f"Exception while running custom-cert.py :\n{e}")

sys_exit(status)
