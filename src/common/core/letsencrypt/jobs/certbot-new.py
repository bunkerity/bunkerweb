#!/usr/bin/env python3

from itertools import chain
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from subprocess import DEVNULL, STDOUT, Popen, run, PIPE
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from re import MULTILINE, search

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("LETS-ENCRYPT.new", getenv("LOG_LEVEL", "INFO"))
LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT.new.certbot", getenv("LOG_LEVEL", "INFO"))
status = 0

CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")

DATA_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc")
LETS_ENCRYPT_JOBS_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt", "jobs")
LETS_ENCRYPT_WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LETS_ENCRYPT_LOGS_DIR = join(sep, "var", "log", "bunkerweb")


def certbot_new(domains: str, email: str, use_letsencrypt_staging: bool = False, *, force: bool = False) -> int:
    process = Popen(
        [
            CERTBOT_BIN,
            "certonly",
            "--config-dir",
            DATA_PATH.as_posix(),
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
        + (["--staging"] if use_letsencrypt_staging else [])
        + (["--force-renewal"] if force else []),
        stdin=DEVNULL,
        stderr=PIPE,
        universal_newlines=True,
        env=environ | {"PYTHONPATH": join(sep, "usr", "share", "bunkerweb", "deps", "python")},
    )
    while process.poll() is None:
        if process.stderr:
            for line in process.stderr:
                LOGGER_CERTBOT.info(line.strip())
    return process.returncode


status = 0

try:
    # Check if we're using let's encrypt
    use_letsencrypt = False
    is_multisite = getenv("MULTISITE", "no") == "yes"
    all_domains = getenv("SERVER_NAME", "").lower()
    server_names = all_domains.split(" ")

    if getenv("AUTO_LETS_ENCRYPT", "no") == "yes":
        use_letsencrypt = True
    elif is_multisite:
        for first_server in server_names:
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) == "yes":
                use_letsencrypt = True
                break

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping generation...")
        sys_exit(0)
    elif not all_domains:
        LOGGER.warning("There are no server names, skipping generation...")
        sys_exit(0)

    JOB = Job(LOGGER)

    # Restore Let's Encrypt data from db cache
    JOB.restore_cache(job_name="certbot-renew")

    domains_to_ask = {}
    # Multisite case
    if is_multisite:
        domains_server_names = {}

        for first_server in server_names:
            if not first_server or getenv(f"{first_server}_AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
                continue
            domains_server_names[first_server] = getenv(f"{first_server}_SERVER_NAME", first_server).lower()
    # Singlesite case
    else:
        domains_server_names = {server_names[0]: all_domains}

    proc = run(
        [
            CERTBOT_BIN,
            "certificates",
            "--config-dir",
            DATA_PATH.as_posix(),
            "--work-dir",
            LETS_ENCRYPT_WORK_DIR,
            "--logs-dir",
            LETS_ENCRYPT_LOGS_DIR,
        ],
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        env=environ | {"PYTHONPATH": join(sep, "usr", "share", "bunkerweb", "deps", "python")},
        check=False,
    )
    stdout = proc.stdout

    generated_domains = set()

    if proc.returncode != 0:
        LOGGER.error(f"Error while checking certificates :\n{proc.stdout}")
        domains_to_ask = {domain: True for domain in server_names}
    else:
        for first_server, domains in domains_server_names.items():
            generated_domains.update(domains.split(" "))

            current_domains = search(rf"Domains: {first_server}(?P<domains>.*)\n\s*Expiry Date: (?P<expiry_date>.*)$$", stdout, MULTILINE)
            if not current_domains:
                domains_to_ask[first_server] = False
                continue
            elif set(f"{first_server}{current_domains.groupdict()['domains']}".strip().split(" ")) != set(domains.split(" ")):
                LOGGER.warning(f"Domains for {first_server} are not the same as in the certificate, asking new certificate...")
                domains_to_ask[first_server] = True
                continue
            elif ("TEST_CERT" in current_domains.groupdict()['expiry_date'] and getenv(f"{first_server}_")):
                LOGGER.warning(f"Certificate environment (staging/production) changed for {first_server}, asking new certificate...")
            use_letsencrypt_staging = getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes"
            if ("TEST_CERT" in current_domains.groupdict()['expiry_date'] and not use_letsencrypt_staging) or ("TEST_CERT" not in current_domains.groupdict()['expiry_date'] and use_letsencrypt_staging):
                LOGGER.warning(f"Certificate environment (staging/production) changed for {first_server}, asking new certificate...")
                domains_to_ask[first_server] = True
            LOGGER.info(f"Certificates already exists for domain(s) {domains}")

    for first_server, domains in domains_server_names.items():
        if first_server not in domains_to_ask:
            continue

        real_email = getenv(f"{first_server}_EMAIL_LETS_ENCRYPT", getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}"))
        if not real_email:
            real_email = f"contact@{first_server}"

        use_letsencrypt_staging = getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes"

        LOGGER.info(f"Asking certificates for domain(s) : {domains} (email = {real_email}) to Let's Encrypt {'staging ' if use_letsencrypt_staging else ''}...")
        if certbot_new(domains.replace(" ", ","), real_email, use_letsencrypt_staging, force=domains_to_ask[first_server]) != 0:
            status = 2
            LOGGER.error(f"Certificate generation failed for domain(s) {domains} ...")
            continue
        else:
            status = 1 if status == 0 else status
            LOGGER.info(f"Certificate generation succeeded for domain(s) : {domains}")

    # Remove old certificates
    if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
        LOGGER.info("Clear old certificates is activated, removing old / no longer used certificates...")
        for elem in chain(DATA_PATH.glob("archive/*"), DATA_PATH.glob("live/*"), DATA_PATH.glob("renewal/*")):
            if elem.name.replace(".conf", "") not in generated_domains and elem.name != "README":
                LOGGER.warning(f"Removing old certificate {elem}")
                if elem.is_dir():
                    rmtree(elem, ignore_errors=True)
                else:
                    elem.unlink(missing_ok=True)

    # Save Let's Encrypt data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH, job_name="certbot-renew")
        if not cached:
            LOGGER.error(f"Error while saving Let's Encrypt data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved Let's Encrypt data to db cache")
except SystemExit as e:
    status = e.code
except:
    status = 3
    LOGGER.error(f"Exception while running certbot-new.py :\n{format_exc()}")

sys_exit(status)
