#!/usr/bin/python3

from os import environ, getenv, makedirs, remove
from os.path import isfile
from shutil import copy
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/usr/share/bunkerweb/deps/python")
sys_path.append("/usr/share/bunkerweb/utils")
sys_path.append("/usr/share/bunkerweb/db")

from Database import Database
from jobs import file_hash
from logger import setup_logger

logger = setup_logger("CUSTOM-CERT", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)


def check_cert(cert_path, key_path, first_server: str = None) -> bool:
    try:
        if not cert_path or not key_path:
            logger.warning(
                "Both variables CUSTOM_HTTPS_CERT and CUSTOM_HTTPS_KEY have to be set to use custom certificates"
            )
            return False
        elif not isfile(cert_path):
            logger.warning(
                f"Certificate file {cert_path} is not a valid file, ignoring the custom certificate"
            )
            return False

        cert_cache_path = (
            f"/var/cache/bunkerweb/customcert/{cert_path.replace('/', '_')}.hash"
        )
        cert_hash = file_hash(cert_path)

        if not isfile(cert_cache_path):
            with open(cert_cache_path, "w") as f:
                f.write(cert_hash)

        old_hash = file_hash(cert_cache_path)
        if old_hash == cert_hash:
            return False

        with open(cert_cache_path, "w") as f:
            f.write(cert_hash)

        copy(cert_path, cert_cache_path.replace(".hash", ""))

        if not isfile(key_path):
            logger.warning(
                f"Key file {key_path} is not a valid file, removing the custom certificate ..."
            )
            remove(cert_path)
            remove(cert_cache_path)
            return False

        key_cache_path = (
            f"/var/cache/bunkerweb/customcert/{key_path.replace('/', '_')}.hash"
        )
        key_hash = file_hash(key_path)

        if not isfile(key_cache_path):
            with open(key_cache_path, "w") as f:
                f.write(key_hash)

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
        for first_server in getenv("SERVER_NAME").split(" "):
            if not first_server or (
                getenv(
                    f"{first_server}_USE_CUSTOM_HTTPS", getenv("USE_CUSTOM_HTTPS", "no")
                )
                != "yes"
            ):
                continue

            cert_path = getenv(
                f"{first_server}_CUSTOM_HTTPS_CERT", getenv("CUSTOM_HTTPS_CERT", "")
            )
            key_path = getenv(
                f"{first_server}_CUSTOM_HTTPS_KEY", getenv("CUSTOM_HTTPS_KEY", "")
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
    elif getenv("USE_CUSTOM_HTTPS") == "yes" and getenv("SERVER_NAME") != "":
        cert_path = getenv("CUSTOM_HTTPS_CERT", "")
        key_path = getenv("CUSTOM_HTTPS_KEY", "")

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
