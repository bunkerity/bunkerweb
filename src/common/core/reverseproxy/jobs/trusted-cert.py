#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from tempfile import NamedTemporaryFile
from traceback import format_exc
from typing import Tuple, Union, Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("REVERSE-PROXY.trusted-cert")
JOB = Job(LOGGER, __file__)

CACHE_NAME = "trusted-ca.pem"


def process_ca_data(data: str, file_path: Optional[str], server_name: str) -> Union[bytes, Path, None]:
    """Resolve the trusted CA from a file path or from direct data (base64 or plain PEM)."""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"Trusted certificate file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        # If the data already looks like PEM, use it directly.
        text_data = data.encode()
        if text_data.strip().startswith(b"-----BEGIN"):
            if not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                LOGGER.error(f"Invalid trusted certificate format for server {server_name}")
                return None
            return text_data

        # Try strict base64 decode (strip whitespace, pad if needed).
        try:
            base64_data = "".join(data.split())
            base64_data += "=" * (-len(base64_data) % 4)
            decoded = b64decode(base64_data, validate=True)
            if not decoded.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                raise ValueError("decoded trusted certificate data is not PEM")
            return decoded
        except BaseException:
            LOGGER.debug(format_exc())
            LOGGER.warning(f"Failed to decode trusted certificate data as base64 for server {server_name}, trying as plain text")
            if not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                LOGGER.error(f"Invalid trusted certificate format for server {server_name}")
                return None
            return text_data
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing trusted certificate for {server_name}: {e}")
        return None


def check_ca(ca_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    """Validate the CA bundle with OpenSSL and cache it (disk + DB) for distribution to instances."""
    try:
        if isinstance(ca_file, Path):
            if not ca_file.is_file():
                return False, f"Trusted certificate file {ca_file} is not a valid file, ignoring"
            ca_file = ca_file.read_bytes()

        with NamedTemporaryFile(delete=False) as ca_temp:
            try:
                ca_temp.write(ca_file)
                ca_temp.flush()
                result = run(
                    ["openssl", "x509", "-noout", "-in", ca_temp.name],
                    stdin=DEVNULL,
                    stderr=DEVNULL,
                    check=False,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
                if result.returncode != 0:
                    return False, "Trusted certificate is invalid."
            finally:
                Path(ca_temp.name).unlink(missing_ok=True)

        ca_hash = bytes_hash(ca_file)
        old_hash = JOB.cache_hash(CACHE_NAME, service_id=first_server)
        ca_path = Path(sep, "var", "cache", "bunkerweb", "reverseproxy", first_server, CACHE_NAME)
        if old_hash == ca_hash and ca_path.is_file():
            return False, ""

        cached, err = JOB.cache_file(CACHE_NAME, ca_file, service_id=first_server, checksum=ca_hash, delete_file=False)
        if not cached:
            LOGGER.error(f"Error while caching trusted certificate for {first_server} : {err}")
            return False, err
        return True, ""
    except BaseException as e:
        return False, e


status = 0

try:
    all_domains = getenv("SERVER_NAME", "www.example.com") or []
    multisite = getenv("MULTISITE", "no") == "yes"

    if isinstance(all_domains, str):
        all_domains = all_domains.split()

    if not all_domains:
        LOGGER.info("No services found, exiting ...")
        sys_exit(0)

    def _get(server: str, key: str, default: str = "") -> str:
        return getenv(f"{server}_{key}", default) if multisite else getenv(key, default)

    skipped_servers = []
    for first_server in all_domains:
        if _get(first_server, "USE_REVERSE_PROXY", "no") != "yes" or _get(first_server, "REVERSE_PROXY_SSL_VERIFY", "no") != "yes":
            skipped_servers.append(first_server)
            continue

        priority = _get(first_server, "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY", "file")
        ca_path = _get(first_server, "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE")
        ca_data = _get(first_server, "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA")

        # No CA configured: upstream verification falls back to the system CA store, nothing to cache.
        if not ca_path and not ca_data:
            LOGGER.info(f"Service {first_server} verifies the upstream against the system CA store (no trusted certificate set)")
            skipped_servers.append(first_server)
            continue

        use_file = priority == "file" and ca_path
        ca_file = process_ca_data(ca_data if not use_file else "", ca_path if use_file else None, first_server)
        if not ca_file:
            LOGGER.warning(f"No valid trusted certificate for {first_server}; upstream verification will be disabled for that server")
            skipped_servers.append(first_server)
            status = 2
            continue

        LOGGER.info(f"Checking trusted certificate for {first_server} ...")
        need_reload, err = check_ca(ca_file, first_server)
        if isinstance(err, BaseException):
            LOGGER.error(f"Exception while checking {first_server}'s trusted certificate, skipping ... \n{err}")
            skipped_servers.append(first_server)
            status = 2
            continue
        elif err:
            LOGGER.warning(f"Error while checking {first_server}'s trusted certificate : {err}")
            skipped_servers.append(first_server)
            status = 2
            continue
        elif need_reload:
            LOGGER.info(f"Detected change in {first_server}'s trusted certificate")
            status = 1
            continue

        LOGGER.info(f"No change in {first_server}'s trusted certificate")

    for first_server in skipped_servers:
        JOB.del_cache(CACHE_NAME, service_id=first_server)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running trusted-cert.py :\n{e}")

sys_exit(status)
