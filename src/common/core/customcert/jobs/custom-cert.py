#!/usr/bin/python3

from os import getenv, sep
from os.path import join, normpath
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Optional

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from jobs import cache_file, cache_hash, file_hash
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore

logger = setup_logger("CUSTOM-CERT", getenv("LOG_LEVEL", "INFO"))
db = None


def check_cert(
    cert_path: str, key_path: str, first_server: Optional[str] = None
) -> bool:
    try:
        if not cert_path or not key_path:
            logger.warning(
                "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"
            )
            return False

        cert_path = Path(normpath(cert_path))
        key_path = Path(normpath(key_path))

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

        cert_cache_path = Path(
            sep,
            "var",
            "cache",
            "bunkerweb",
            "customcert",
            first_server or "",
            "cert.pem",
        )
        cert_cache_path.parent.mkdir(parents=True, exist_ok=True)

        cert_hash = file_hash(cert_path)
        old_hash = cache_hash(cert_cache_path, db)
        if old_hash == cert_hash:
            return False

        cached, err = cache_file(
            cert_path, cert_cache_path, cert_hash, db, delete_file=False
        )
        if not cached:
            logger.error(f"Error while caching custom-cert cert.pem file : {err}")

        key_cache_path = Path(
            sep,
            "var",
            "cache",
            "bunkerweb",
            "customcert",
            first_server or "",
            "key.pem",
        )
        key_cache_path.parent.mkdir(parents=True, exist_ok=True)

        key_hash = file_hash(key_path)
        old_hash = cache_hash(key_cache_path, db)
        if old_hash != key_hash:
            cached, err = cache_file(
                key_path, key_cache_path, key_hash, db, delete_file=False
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
    Path(sep, "var", "cache", "bunkerweb", "customcert").mkdir(
        parents=True, exist_ok=True
    )

    # Multisite case
    if getenv("MULTISITE") == "yes":
        servers = getenv("SERVER_NAME") or []

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if not first_server or (
                getenv(f"{first_server}_USE_CUSTOM_SSL", getenv("USE_CUSTOM_SSL", "no"))
                != "yes"
            ):
                continue

            if not db:
                db = Database(
                    logger,
                    sqlalchemy_string=getenv("DATABASE_URI", None),
                )

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
        db = Database(
            logger,
            sqlalchemy_string=getenv("DATABASE_URI", None),
        )

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
