#!/usr/bin/python3

from os import _exit, environ, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from tarfile import open as tar_open
from io import BytesIO
from shutil import rmtree

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("api",),
        ("utils",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger  # type: ignore

from jobs import get_cache, cache_file


def renew(domain: str, letsencrypt_path: Path) -> int:
    return run(
        [
            join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot"),
            "renew",
            "--config-dir",
            str(letsencrypt_path.joinpath("etc")),
            "--work-dir",
            join(sep, "var", "lib", "bunkerweb", "letsencrypt"),
            "--logs-dir",
            join(sep, "var", "log", "bunkerweb"),
            "--cert-name",
            domain,
            "--deploy-hook",
            join(
                sep,
                "usr",
                "share",
                "bunkerweb",
                "core",
                "letsencrypt",
                "jobs",
                "certbot-deploy.py",
            ),
        ],
        stdin=DEVNULL,
        stderr=STDOUT,
        env=environ.copy()
        | {"PYTHONPATH": join(sep, "usr", "share", "bunkerweb", "deps", "python")},
        check=False,
    ).returncode


LOGGER = setup_logger("LETS-ENCRYPT.renew", getenv("LOG_LEVEL", "INFO"))
CORE_API = API(getenv("API_ADDR", ""), "job-certbot-renew")
API_TOKEN = getenv("API_TOKEN", None)
status = 0

try:
    # Check if we're using let's encrypt
    use_letsencrypt = False
    if getenv("AUTO_LETS_ENCRYPT", "no") == "yes":
        use_letsencrypt = True
    elif getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if (
                first_server
                and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes"
            ):
                use_letsencrypt = True
                break

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping renew...")
        _exit(0)

    # Create directory if it doesn't exist
    letsencrypt_path = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
    letsencrypt_path.mkdir(parents=True, exist_ok=True)
    Path(sep, "var", "lib", "bunkerweb", "letsencrypt").mkdir(
        parents=True, exist_ok=True
    )

    tgz = get_cache("folder.tgz", CORE_API, API_TOKEN)
    if tgz:
        # Delete folder if needed
        if letsencrypt_path.exists():
            rmtree(str(letsencrypt_path), ignore_errors=True)
        letsencrypt_path.mkdir(parents=True, exist_ok=True)
        # Extract it
        with tar_open(name="folder.tgz", mode="r:gz", fileobj=BytesIO(tgz)) as tf:
            tf.extractall(str(letsencrypt_path))
        LOGGER.info("Successfully retrieved Let's Encrypt data from db cache")
    else:
        LOGGER.info("No Let's Encrypt data found in db cache")

    if getenv("MULTISITE", "no") == "yes":
        servers = getenv("SERVER_NAME") or []

        if isinstance(servers, str):
            servers = servers.split(" ")

        for first_server in servers:
            if (
                not first_server
                or getenv(
                    f"{first_server}_AUTO_LETS_ENCRYPT",
                    getenv("AUTO_LETS_ENCRYPT", "no"),
                )
                != "yes"
                or not letsencrypt_path.joinpath(
                    "etc", "live", first_server, "cert.pem"
                ).exists()
            ):
                continue

            if renew(first_server, letsencrypt_path) != 0:
                status = 2
                LOGGER.error(
                    f"Certificates renewal for {first_server} failed",
                )
    elif getenv("AUTO_LETS_ENCRYPT", "no") == "yes" and getenv("SERVER_NAME", ""):
        first_server = getenv("SERVER_NAME", "").split(" ")[0]
        if letsencrypt_path.joinpath("etc", "live", first_server, "cert.pem").exists():
            if renew(first_server, letsencrypt_path) != 0:
                status = 2
                LOGGER.error(
                    f"Certificates renewal for {first_server} failed",
                )

    # Put new folder in cache
    bio = BytesIO()
    with tar_open("folder.tgz", mode="w:gz", fileobj=bio, compresslevel=9) as tgz:
        tgz.add(str(letsencrypt_path), arcname=".")
    bio.seek(0, 0)

    # Put tgz in cache
    cached, err = cache_file("folder.tgz", bio.read(), CORE_API, API_TOKEN)

    if not cached:
        LOGGER.error(f"Error while saving Let's Encrypt data to db cache : {err}")
    else:
        LOGGER.info("Successfully saved Let's Encrypt data to db cache")
except:
    status = 2
    LOGGER.error(f"Exception while running certbot-renew.py :\n{format_exc()}")

sys_exit(status)
