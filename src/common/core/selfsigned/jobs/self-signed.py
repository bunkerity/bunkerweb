#!/usr/bin/python3

from os import getenv
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/db",
    )
)

from Database import Database
from logger import setup_logger

logger = setup_logger("self-signed", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)


def generate_cert(first_server, days, subj):
    if Path(f"/var/cache/bunkerweb/selfsigned/{first_server}.pem").is_file():
        cmd = f"openssl x509 -checkend 86400 -noout -in /var/cache/bunkerweb/selfsigned/{first_server}.pem"
        proc = run(cmd.split(" "), stdin=DEVNULL, stderr=STDOUT)
        if proc.returncode == 0:
            logger.info(f"Self-signed certificate already present for {first_server}")
            return True, 0

    logger.info(f"Generating self-signed certificate for {first_server}")
    cmd = f"openssl req -nodes -x509 -newkey rsa:4096 -keyout /var/cache/bunkerweb/selfsigned/{first_server}.key -out /var/cache/bunkerweb/selfsigned/{first_server}.pem -days {days} -subj {subj}"
    proc = run(cmd.split(" "), stdin=DEVNULL, stderr=STDOUT)
    if proc.returncode != 0:
        logger.error(f"Self-signed certificate generation failed for {first_server}")
        return False, 2

    # Update db
    with open(f"/var/cache/bunkerweb/selfsigned/{first_server}.key", "r") as f:
        key_data = f.read().encode("utf-8")

    err = db.update_job_cache(
        "self-signed", first_server, f"{first_server}.key", key_data
    )

    if err:
        logger.warning(f"Couldn't update db cache for {first_server}.key file: {err}")

    with open(f"/var/cache/bunkerweb/selfsigned/{first_server}.pem", "r") as f:
        pem_data = f.read().encode("utf-8")

    err = db.update_job_cache(
        "self-signed", first_server, f"{first_server}.pem", pem_data
    )

    if err:
        logger.warning(f"Couldn't update db cache for {first_server}.pem file: {err}")

    logger.info(f"Successfully generated self-signed certificate for {first_server}")
    return True, 1


status = 0

try:
    Path("/var/cache/bunkerweb/selfsigned/").mkdir(parents=True, exist_ok=True)

    # Multisite case
    if getenv("MULTISITE") == "yes":
        servers = getenv("SERVER_NAME", [])

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if (
                not first_server
                or getenv(
                    f"{first_server}_GENERATE_SELF_SIGNED_SSL",
                    getenv("GENERATE_SELF_SIGNED_SSL", "no"),
                )
                != "yes"
                or Path(f"/var/cache/bunkerweb/selfsigned/{first_server}.pem").is_file()
            ):
                continue

            ret, ret_status = generate_cert(
                first_server,
                getenv(
                    f"{first_server}_SELF_SIGNED_SSL_EXPIRY",
                    getenv("SELF_SIGNED_SSL_EXPIRY", "365"),
                ),
                getenv(
                    f"{first_server}_SELF_SIGNED_SSL_SUBJ",
                    getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
                ),
            )
            if not ret:
                status = ret_status
            elif ret_status == 1 and ret_status != 2:
                status = 1

    # Singlesite case
    elif getenv("GENERATE_SELF_SIGNED_SSL", "no") == "yes" and getenv("SERVER_NAME"):
        first_server = getenv("SERVER_NAME", "").split(" ")[0]
        ret, ret_status = generate_cert(
            first_server,
            getenv("SELF_SIGNED_SSL_EXPIRY", "365"),
            getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
        )
        if not ret:
            status = ret_status
        elif ret_status == 1 and ret_status != 2:
            status = 1

except:
    status = 2
    logger.error(f"Exception while running self-signed.py :\n{format_exc()}")

sys_exit(status)
