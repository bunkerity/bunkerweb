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
        ("utils",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import get_file_in_db, set_file_in_db

logger = setup_logger("LETS-ENCRYPT.new", getenv("LOG_LEVEL", "INFO"))
status = 0


def certbot_new(
    domains: str, email: str, letsencrypt_path: Path, letsencrypt_job_path: Path
) -> int:
    return run(
        [
            join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot"),
            "certonly",
            "--config-dir",
            str(letsencrypt_path.joinpath("etc")),
            "--work-dir",
            str(letsencrypt_path.joinpath("lib")),
            "--logs-dir",
            str(letsencrypt_path.joinpath("log")),
            "--manual",
            "--preferred-challenges=http",
            "--manual-auth-hook",
            str(letsencrypt_job_path.joinpath("certbot-auth.py")),
            "--manual-cleanup-hook",
            str(letsencrypt_job_path.joinpath("certbot-cleanup.py")),
            "-n",
            "-d",
            domains,
            "--email",
            email,
            "--agree-tos",
        ]
        + (["--staging"] if getenv("USE_LETS_ENCRYPT_STAGING", "no") == "yes" else []),
        stdin=DEVNULL,
        stderr=STDOUT,
        env=environ.copy()
        | {"PYTHONPATH": join(sep, "usr", "share", "bunkerweb", "deps", "python")},
        check=True,
    ).returncode


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
        logger.info("Let's Encrypt is not activated, skipping generation...")
        _exit(0)

    # Create directory if it doesn't exist
    letsencrypt_path = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
    letsencrypt_job_path = Path(
        sep, "usr", "share", "bunkerweb", "core", "letsencrypt", "jobs"
    )
    letsencrypt_path.mkdir(parents=True, exist_ok=True)

    # Extract letsencrypt folder if it exists in db
    db = Database(
        logger,
        sqlalchemy_string=getenv("DATABASE_URI", None),
    )

    tgz = get_file_in_db("folder.tgz", db, job_name="certbot-renew")
    if tgz:
        # Delete folder if needed
        if letsencrypt_path.exists():
            rmtree(str(letsencrypt_path), ignore_errors=True)
        letsencrypt_path.mkdir(parents=True, exist_ok=True)
        # Extract it
        with tar_open(name="folder.tgz", mode="r:gz", fileobj=BytesIO(tgz)) as tf:
            tf.extractall(str(letsencrypt_path))
        logger.info("Successfully retrieved Let's Encrypt data from db cache")
    else:
        logger.info("No Let's Encrypt data found in db cache")

    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "").split(" "):
            if (
                not first_server
                or getenv(
                    f"{first_server}_AUTO_LETS_ENCRYPT",
                    getenv("AUTO_LETS_ENCRYPT", "no"),
                )
                != "yes"
            ):
                continue

            domains = getenv(f"{first_server}_SERVER_NAME", first_server).replace(
                " ", ","
            )

            if letsencrypt_path.joinpath(first_server, "cert.pem").exists():
                logger.info(
                    f"Certificates already exists for domain(s) {domains}",
                )
                continue

            real_email = getenv(
                f"{first_server}_EMAIL_LETS_ENCRYPT",
                getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}"),
            )
            if not real_email:
                real_email = f"contact@{first_server}"

            logger.info(
                f"Asking certificates for domains : {domains} (email = {real_email}) ...",
            )
            if (
                certbot_new(domains, real_email, letsencrypt_path, letsencrypt_job_path)
                != 0
            ):
                logger.error(
                    f"Certificate generation failed for domain(s) {domains} ...",
                )
                _exit(2)
            else:
                status = 1
                logger.info(
                    f"Certificate generation succeeded for domain(s) : {domains}"
                )

    # Singlesite case
    elif getenv("AUTO_LETS_ENCRYPT", "no") == "yes" and getenv("SERVER_NAME"):
        first_server = getenv("SERVER_NAME", "").split(" ")[0]
        domains = getenv("SERVER_NAME", "").replace(" ", ",")

        if letsencrypt_path.joinpath("etc", "live", first_server, "cert.pem").exists():
            logger.info(f"Certificates already exists for domain(s) {domains}")
        else:
            real_email = getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}")
            if not real_email:
                real_email = f"contact@{first_server}"

            logger.info(
                f"Asking certificates for domain(s) : {domains} (email = {real_email}) ...",
            )
            if (
                certbot_new(domains, real_email, letsencrypt_path, letsencrypt_job_path)
                != 0
            ):
                status = 2
                logger.error(f"Certificate generation failed for domain(s) : {domains}")
            else:
                status = 1
                logger.info(
                    f"Certificate generation succeeded for domain(s) : {domains}"
                )

    # Put new folder in cache
    bio = BytesIO()
    with tar_open("folder.tgz", mode="w:gz", fileobj=bio, compresslevel=9) as tgz:
        tgz.add(str(letsencrypt_path), arcname=".")
    bio.seek(0, 0)

    # Put tgz in cache
    cached, err = set_file_in_db("folder.tgz", bio.read(), db, job_name="certbot-renew")

    if not cached:
        logger.error(f"Error while saving Let's Encrypt data to db cache : {err}")
    else:
        logger.info("Successfully saved Let's Encrypt data to db cache")
except:
    status = 3
    logger.error(f"Exception while running certbot-new.py :\n{format_exc()}")

sys_exit(status)
