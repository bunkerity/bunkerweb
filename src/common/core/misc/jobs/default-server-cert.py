#!/usr/bin/env python3

from os import chmod, getenv, sep, replace
from os.path import join
from pathlib import Path
from stat import S_IRUSR, S_IWUSR
from subprocess import DEVNULL, run, PIPE
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from tempfile import NamedTemporaryFile
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("DEFAULT-SERVER-CERT")
status = 0

try:
    JOB = Job(LOGGER, __file__)

    cert_path = Path(sep, "var", "cache", "bunkerweb", "misc")
    if not JOB.is_cached_file("default-server-cert.pem", "month") or not JOB.is_cached_file("default-server-cert.key", "month"):
        LOGGER.info("Generating self-signed certificate for default server")
        cert_path.mkdir(parents=True, exist_ok=True)
        tmp_key_path: Optional[Path] = None
        tmp_cert_path: Optional[Path] = None
        with NamedTemporaryFile(dir=cert_path, prefix="default-server-cert.", suffix=".key", delete=False) as tmp_key:
            tmp_key_path = Path(tmp_key.name)
        with NamedTemporaryFile(dir=cert_path, prefix="default-server-cert.", suffix=".pem", delete=False) as tmp_cert:
            tmp_cert_path = Path(tmp_cert.name)
        assert tmp_key_path is not None and tmp_cert_path is not None

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
                    str(tmp_key_path),
                    "-out",
                    str(tmp_cert_path),
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
                LOGGER.error("Self-signed certificate generation failed for default server")
                LOGGER.error(f"OpenSSL error output: {result.stderr}")
                status = 2
            else:
                LOGGER.info("Successfully generated self-signed certificate for default server")
                replace(tmp_key_path, cert_path.joinpath("default-server-cert.key"))
                replace(tmp_cert_path, cert_path.joinpath("default-server-cert.pem"))
                try:
                    chmod(str(cert_path.joinpath("default-server-cert.key")), S_IRUSR | S_IWUSR)  # 0o600 - read/write for owner only
                except OSError as e:
                    LOGGER.error(f"Error setting permissions on default-server-cert.key: {e}")
                status = 1

                cached, err = JOB.cache_file("default-server-cert.pem", cert_path.joinpath("default-server-cert.pem"), overwrite_file=False)
                if not cached:
                    LOGGER.error(f"Error while saving default-server-cert default-server-cert.pem file to db cache : {err}")
                else:
                    LOGGER.info("Successfully saved default-server-cert default-server-cert.pem file to db cache")

                cached, err = JOB.cache_file("default-server-cert.key", cert_path.joinpath("default-server-cert.key"), overwrite_file=False)
                if not cached:
                    LOGGER.error(f"Error while saving default-server-cert default-server-cert.key file to db cache : {err}")
                else:
                    LOGGER.info("Successfully saved default-server-cert default-server-cert.key file to db cache")
        finally:
            # Clean up the temporary config file
            try:
                Path(config_path).unlink()
            except Exception as e:
                LOGGER.warning(f"Failed to delete temporary OpenSSL config file: {e}")
            if tmp_key_path is not None:
                tmp_key_path.unlink(missing_ok=True)
            if tmp_cert_path is not None:
                tmp_cert_path.unlink(missing_ok=True)
    else:
        LOGGER.info("Skipping generation of self-signed certificate for default server (already present)")
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running default-server-cert.py :\n{e}")

sys_exit(status)
