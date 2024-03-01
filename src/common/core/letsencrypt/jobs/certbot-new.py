#!/usr/bin/env python3

from os import _exit, environ, getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run, PIPE
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from tarfile import open as tar_open
from io import BytesIO
from shutil import rmtree
from re import MULTILINE, search

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
from jobs import get_file_in_db, set_file_in_db  # type: ignore

logger = setup_logger("LETS-ENCRYPT.new", getenv("LOG_LEVEL", "INFO"))
status = 0

CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")

LETS_ENCRYPT_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
LETS_ENCRYPT_JOBS_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt", "jobs")
LETS_ENCRYPT_WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LETS_ENCRYPT_LOGS_DIR = join(sep, "var", "log", "bunkerweb")


def certbot_new(domains: str, email: str, use_letsencrypt_staging: bool = False) -> int:
    return run(
        [
            CERTBOT_BIN,
            "certonly",
            "--config-dir",
            LETS_ENCRYPT_PATH.joinpath("etc").as_posix(),
            "--work-dir",
            LETS_ENCRYPT_WORK_DIR,
            "--logs-dir",
            LETS_ENCRYPT_LOGS_DIR,
            "--manual",
            "--preferred-challenges=http",
            "--manual-auth-hook",
            LETS_ENCRYPT_JOBS_PATH.joinpath("certbot-auth.py").as_posix(),
            "--manual-cleanup-hook",
            LETS_ENCRYPT_JOBS_PATH.joinpath("certbot-cleanup.py").as_posix(),
            "-n",
            "-d",
            domains,
            "--email",
            email,
            "--agree-tos",
            "--expand",
        ]
        + (["--staging"] if use_letsencrypt_staging else []),
        stdin=DEVNULL,
        stderr=STDOUT,
        env=environ.copy() | {"PYTHONPATH": join(sep, "usr", "share", "bunkerweb", "deps", "python")},
    ).returncode


status = 0

try:
    # Check if we're using let's encrypt
    use_letsencrypt = False
    is_multisite = getenv("MULTISITE", "no") == "yes"
    all_domains = getenv("SERVER_NAME", "")
    server_names = all_domains.split(" ")

    if getenv("AUTO_LETS_ENCRYPT", "no") == "yes":
        use_letsencrypt = True
    elif is_multisite:
        for first_server in server_names:
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True
                break

    if not use_letsencrypt:
        logger.info("Let's Encrypt is not activated, skipping generation...")
        _exit(0)
    elif not getenv("SERVER_NAME"):
        logger.warning("There are no server names, skipping generation...")
        _exit(0)

    # Create directories if they doesn't exist
    LETS_ENCRYPT_PATH.mkdir(parents=True, exist_ok=True)
    Path(sep, "var", "lib", "bunkerweb", "letsencrypt").mkdir(parents=True, exist_ok=True)

    # Extract letsencrypt folder if it exists in db
    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"), pool=False)

    tgz = get_file_in_db("folder.tgz", db, job_name="certbot-renew")
    if tgz:
        # Delete folder if needed
        if LETS_ENCRYPT_PATH.exists():
            rmtree(LETS_ENCRYPT_PATH, ignore_errors=True)
        LETS_ENCRYPT_PATH.mkdir(parents=True, exist_ok=True)
        # Extract it
        with tar_open(name="folder.tgz", mode="r:gz", fileobj=BytesIO(tgz)) as tf:
            tf.extractall(LETS_ENCRYPT_PATH)
        logger.info("Successfully retrieved Let's Encrypt data from db cache")
    else:
        logger.info("No Let's Encrypt data found in db cache")

    domains_to_ask = []
    # Multisite case
    if is_multisite:
        domains_sever_names = {}

        for first_server in server_names:
            if not first_server or getenv(f"{first_server}_AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
                continue
            domains_sever_names[first_server] = getenv(f"{first_server}_SERVER_NAME", first_server)
    # Singlesite case
    else:
        domains_sever_names = {server_names[0]: all_domains}

    proc = run(
        [CERTBOT_BIN, "certificates", "--config-dir", LETS_ENCRYPT_PATH.joinpath("etc").as_posix(), "--work-dir", LETS_ENCRYPT_WORK_DIR, "--logs-dir", LETS_ENCRYPT_LOGS_DIR],
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        env=environ.copy() | {"PYTHONPATH": join(sep, "usr", "share", "bunkerweb", "deps", "python")},
    )
    stdout = proc.stdout

    if proc.returncode != 0:
        logger.error(f"Error while checking certificates :\n{proc.stdout}")
        domains_to_ask = server_names
    else:
        for first_server, domains in domains_sever_names.items():
            current_domains = search(rf"Domains: {first_server}(?P<domains>.*)$", stdout, MULTILINE)
            if not current_domains:
                domains_to_ask.append(first_server)
                continue
            elif set(f"{first_server}{current_domains.groupdict()['domains']}".strip().split(" ")) != set(domains.split(" ")):
                logger.warning(f"Domains for {first_server} are not the same as in the certificate, asking new certificate...")
                domains_to_ask.append(first_server)
                continue
            logger.info(f"Certificates already exists for domain(s) {domains}")

    for first_server, domains in domains_sever_names.items():
        if first_server not in domains_to_ask:
            continue

        real_email = getenv(f"{first_server}_EMAIL_LETS_ENCRYPT", getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}"))
        if not real_email:
            real_email = f"contact@{first_server}"

        use_letsencrypt_staging = getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes"

        logger.info(f"Asking certificates for domain(s) : {domains} (email = {real_email}) to Let's Encrypt {'staging ' if use_letsencrypt_staging else ''}...")
        if certbot_new(domains.replace(" ", ","), real_email, use_letsencrypt_staging) != 0:
            status = 2
            logger.error(f"Certificate generation failed for domain(s) {domains} ...")
            continue
        else:
            status = 1 if status == 0 else status
            logger.info(f"Certificate generation succeeded for domain(s) : {domains}")

    # Put new folder in cache
    bio = BytesIO()
    with tar_open("folder.tgz", mode="w:gz", fileobj=bio, compresslevel=9) as tgz:
        tgz.add(LETS_ENCRYPT_PATH, arcname=".")
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
