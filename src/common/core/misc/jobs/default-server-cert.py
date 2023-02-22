#!/usr/bin/python3

from os import getenv, makedirs
from os.path import isfile
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
    )
)

from logger import setup_logger

logger = setup_logger("DEFAULT-SERVER-CERT", getenv("LOG_LEVEL", "INFO"))
status = 0

try:

    # Check if we need to generate a self-signed default cert for non-SNI "clients"
    need_default_cert = False
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            for check_var in (
                "USE_CUSTOM_HTTPS",
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
            getenv("USE_CUSTOM_HTTPS", "no"),
            getenv("AUTO_LETS_ENCRYPT", "no"),
            getenv("GENERATE_SELF_SIGNED_SSL", "no"),
        )
    ):
        need_default_cert = True

    # Generate the self-signed certificate
    if need_default_cert:
        makedirs("/var/cache/bunkerweb/default-server-cert", exist_ok=True)
        if not isfile("/var/cache/bunkerweb/default-server-cert/cert.pem"):
            cmd = "openssl req -nodes -x509 -newkey rsa:4096 -keyout /var/cache/bunkerweb/default-server-cert/cert.key -out /var/cache/bunkerweb/default-server-cert/cert.pem -days 3650".split(
                " "
            )
            cmd.extend(["-subj", "/C=AU/ST=Some-State/O=Internet Widgits Pty Ltd/"])
            proc = run(cmd, stdin=DEVNULL, stderr=STDOUT)
            if proc.returncode != 0:
                logger.error(
                    "Self-signed certificate generation failed for default server",
                )
                status = 2
            else:
                logger.info(
                    "Successfully generated self-signed certificate for default server",
                )
        else:
            logger.info(
                "Skipping generation of self-signed certificate for default server (already present)",
            )
    else:
        logger.info(
            "Skipping generation of self-signed certificate for default server (not needed)",
        )

except:
    status = 2
    logger.error(f"Exception while running default-server-cert.py :\n{format_exc()}")

sys_exit(status)
