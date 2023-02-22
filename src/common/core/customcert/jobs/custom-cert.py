#!/usr/bin/python3

from os import getenv, makedirs
from pathlib import Path
from shutil import copy
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Optional

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/db",
    )
)

from Database import Database
from jobs import file_hash
from logger import setup_logger

logger = setup_logger("CUSTOM-CERT", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)


def check_cert(cert_path, key_path, first_server: Optional[str] = None) -> bool:
    try:
        if not cert_path or not key_path:
            logger.warning(
                "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"
            )
            return False
        elif not Path(cert_path).is_file():
            logger.warning(
                f"Certificate file {cert_path} is not a valid file, ignoring the custom certificate"
            )
            return False
        elif not Path(key_path).is_file():
            logger.warning(
                f"Key file {key_path} is not a valid file, ignoring the custom certificate"
            )
            return False

        cert_cache_path = (
            f"/var/cache/bunkerweb/customcert/{cert_path.replace('/', '_')}.hash"
        )
        cert_hash = file_hash(cert_path)

        if not Path(cert_cache_path).is_file():
            Path(cert_cache_path).write_text(cert_hash)

        old_hash = file_hash(cert_cache_path)
        if old_hash == cert_hash:
            return False

        Path(cert_cache_path).write_text(cert_hash)
        copy(cert_path, cert_cache_path.replace(".hash", ""))

        if not Path(key_path).is_file():
            logger.warning(
                f"Key file {key_path} is not a valid file, removing the custom certificate ..."
            )
            Path(cert_path).unlink()
            Path(cert_cache_path).unlink()
            return False

        key_cache_path = (
            f"/var/cache/bunkerweb/customcert/{key_path.replace('/', '_')}.hash"
        )
        key_hash = file_hash(key_path)

        if not Path(key_cache_path).is_file():
            Path(key_cache_path).write_text(key_hash)

        old_hash = file_hash(key_cache_path)
        if old_hash != key_hash:
            copy(key_path, key_cache_path.replace(".hash", ""))

            with open(key_path, "r") as f:
                err = db.update_job_cache(
                    "custom-cert",
                    first_server,
                    key_cache_path.replace(".hash", "").split("/")[-1],
                    f.read().encode("utf-8"),
                    checksum=key_hash,
                )

            if err:
                logger.warning(
                    f"Couldn't update db cache for {key_path.replace('/', '_')}.hash: {err}"
                )

        with open(cert_path, "r") as f:
            err = db.update_job_cache(
                "custom-cert",
                first_server,
                cert_cache_path.replace(".hash", "").split("/")[-1],
                f.read().encode("utf-8"),
                checksum=cert_hash,
            )

        if err:
            logger.warning(
                f"Couldn't update db cache for {cert_path.replace('/', '_')}.hash: {err}"
            )

        return True
    except:
        logger.error(
            f"Exception while running custom-cert.py (check_cert) :\n{format_exc()}",
        )
    return False


status = 0

try:
    makedirs("/var/cache/bunkerweb/customcert/", exist_ok=True)

    # Multisite case
    if getenv("MULTISITE") == "yes":
        servers = getenv("SERVER_NAME", [])

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if not first_server or (
                getenv(
                    f"{first_server}_USE_CUSTOM_SSL", getenv("USE_CUSTOM_SSL", "no")
                )
                != "yes"
            ):
                continue

            cert_path = getenv(
                f"{first_server}_CUSTOM_SSL_CERT", getenv("CUSTOM_SSL_CERT", "")
            )
            key_path = getenv(
                f"{first_server}_CUSTOM_SSL_KEY", getenv("CUSTOM_SSL_KEY", "")
            )

            logger.info(
                f"Checking certificate {cert_path} ...",
            )
            need_reload = check_cert(cert_path, key_path, first_server)
            if need_reload:
                logger.info(
                    f"Detected change for certificate {cert_path}",
                )
                status = 1
            else:
                logger.info(
                    f"No change for certificate {cert_path}",
                )
    # Singlesite case
    elif getenv("USE_CUSTOM_SSL") == "yes" and getenv("SERVER_NAME") != "":
        cert_path = getenv("CUSTOM_SSL_CERT", "")
        key_path = getenv("CUSTOM_SSL_KEY", "")

        logger.info(f"Checking certificate {cert_path} ...")
        need_reload = check_cert(cert_path, key_path)
        if need_reload:
            logger.info(f"Detected change for certificate {cert_path}")
            status = 1
        else:
            logger.info(f"No change for certificate {cert_path}")

except:
    status = 2
    logger.error(f"Exception while running custom-cert.py :\n{format_exc()}")

sys_exit(status)
