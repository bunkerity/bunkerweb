#!/usr/bin/env python3

from os import chmod, getenv, sep
from os.path import join
from pathlib import Path
from stat import S_IRUSR, S_IWUSR
from subprocess import DEVNULL, run, PIPE
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from tempfile import NamedTemporaryFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("API-SERVER-CERT")
status = 0

try:
    JOB = Job(LOGGER, __file__)

    if getenv("API_LISTEN_HTTPS", "no").strip() != "yes":
        LOGGER.info("Skipping the generation of self-signed certificate for API server (disabled)")
        sys_exit(status)

    cert_path = Path(sep, "var", "cache", "bunkerweb", "misc")
    if not JOB.is_cached_file("api-server-cert.pem", "month") or not JOB.is_cached_file("api-server-cert.key", "month"):
        LOGGER.info("Generating self-signed certificate for API server")
        cert_path.mkdir(parents=True, exist_ok=True)

        # Create a temporary OpenSSL config file with enhanced security settings
        with NamedTemporaryFile(mode="w", delete=False) as config_file:
            config_content = """
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = AU
ST = Some-State
O = Internet Widgits Pty Ltd
CN = www.example.org

[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment, keyAgreement
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
basicConstraints = critical, CA:false

[alt_names]
DNS.1 = www.example.org
"""
            # Remove any leading whitespace which can cause parsing issues
            config_content = "\n".join(line.lstrip() for line in config_content.split("\n"))
            config_file.write(config_content)
            config_file.flush()  # Ensure content is written to disk
            config_path = config_file.name

        try:
            result = run(
                [
                    "openssl",
                    "req",
                    "-nodes",
                    "-x509",
                    "-newkey",
                    "ec",
                    "-pkeyopt",
                    "ec_paramgen_curve:secp384r1",
                    "-keyout",
                    str(cert_path.joinpath("api-server-cert.key")),
                    "-out",
                    str(cert_path.joinpath("api-server-cert.pem")),
                    "-days",
                    "3650",
                    "-sha512",
                    "-config",
                    config_path,
                ],
                stdin=DEVNULL,
                stderr=PIPE,
                stdout=PIPE,
                text=True,
                check=False,
                env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
            )

            if result.returncode != 0:
                LOGGER.error("Self-signed certificate generation failed for API server")
                LOGGER.error(f"OpenSSL error output: {result.stderr}")
                status = 2
            else:
                LOGGER.info("Successfully generated self-signed certificate for API server")
                try:
                    chmod(str(cert_path.joinpath("api-server-cert.key")), S_IRUSR | S_IWUSR)  # 0o600 - read/write for owner only
                except OSError as e:
                    LOGGER.error(f"Error setting permissions on api-server-cert.key: {e}")
                status = 1

                cached, err = JOB.cache_file("api-server-cert.pem", cert_path.joinpath("api-server-cert.pem"), overwrite_file=False)
                if not cached:
                    LOGGER.error(f"Error while saving api-server-cert api-server-cert.pem file to db cache : {err}")
                else:
                    LOGGER.info("Successfully saved api-server-cert api-server-cert.pem file to db cache")

                cached, err = JOB.cache_file("api-server-cert.key", cert_path.joinpath("api-server-cert.key"), overwrite_file=False)
                if not cached:
                    LOGGER.error(f"Error while saving api-server-cert api-server-cert.key file to db cache : {err}")
                else:
                    LOGGER.info("Successfully saved api-server-cert api-server-cert.key file to db cache")
        finally:
            # Clean up the temporary config file
            try:
                Path(config_path).unlink()
            except Exception as e:
                LOGGER.warning(f"Failed to delete temporary OpenSSL config file: {e}")
    else:
        LOGGER.info("Skipping generation of self-signed certificate for API server (already present)")
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running api-server-cert.py :\n{e}")

sys_exit(status)
