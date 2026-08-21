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

LOGGER = getLogger("MTLS.client-cert")
JOB = Job(LOGGER, __file__)

CA_CACHE_NAME = "ca.pem"
CRL_CACHE_NAME = "crl.pem"


def process_pem_data(data: str, file_path: Optional[str], kind: str, server_name: str) -> Union[bytes, Path, None]:
    """Resolve a client CA bundle or CRL from a file path or from direct data (base64 or plain PEM)."""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{kind} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        marker = b"-----BEGIN X509 CRL-----" if kind == "CRL" else b"-----BEGIN CERTIFICATE-----"

        # If the data already looks like PEM, use it directly.
        text_data = data.encode()
        if text_data.strip().startswith(b"-----BEGIN"):
            if not text_data.strip().startswith(marker):
                LOGGER.error(f"Invalid {kind} format for server {server_name}")
                return None
            return text_data

        # Try strict base64 decode (strip whitespace, pad if needed).
        try:
            base64_data = "".join(data.split())
            base64_data += "=" * (-len(base64_data) % 4)
            decoded = b64decode(base64_data, validate=True)
            if not decoded.strip().startswith(marker):
                raise ValueError(f"decoded {kind} data is not PEM")
            return decoded
        except BaseException:
            LOGGER.debug(format_exc())
            LOGGER.warning(f"Failed to decode {kind} data as base64 for server {server_name}, trying as plain text")
            if not text_data.strip().startswith(marker):
                LOGGER.error(f"Invalid {kind} format for server {server_name}")
                return None
            return text_data
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {kind} for {server_name}: {e}")
        return None


def check_ca(ca_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    """Validate the client CA bundle with OpenSSL and cache it (disk + DB) for distribution to instances."""
    try:
        if isinstance(ca_file, Path):
            if not ca_file.is_file():
                return False, f"Client CA bundle file {ca_file} is not a valid file, ignoring"
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
                    return False, "Client CA bundle is invalid."
            finally:
                Path(ca_temp.name).unlink(missing_ok=True)

        ca_hash = bytes_hash(ca_file)
        old_hash = JOB.cache_hash(CA_CACHE_NAME, service_id=first_server)
        ca_path = Path(sep, "var", "cache", "bunkerweb", "mtls", first_server, CA_CACHE_NAME)
        if old_hash == ca_hash and ca_path.is_file():
            return False, ""

        cached, err = JOB.cache_file(CA_CACHE_NAME, ca_file, service_id=first_server, checksum=ca_hash, delete_file=False)
        if not cached:
            LOGGER.error(f"Error while caching client CA bundle for {first_server} : {err}")
            return False, err
        return True, ""
    except BaseException as e:
        return False, e


def check_crl(crl_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    """Validate the CRL with OpenSSL and cache it (disk + DB) for distribution to instances."""
    try:
        if isinstance(crl_file, Path):
            if not crl_file.is_file():
                return False, f"CRL file {crl_file} is not a valid file, ignoring"
            crl_file = crl_file.read_bytes()

        with NamedTemporaryFile(delete=False) as crl_temp:
            try:
                crl_temp.write(crl_file)
                crl_temp.flush()
                result = run(
                    ["openssl", "crl", "-noout", "-in", crl_temp.name],
                    stdin=DEVNULL,
                    stderr=DEVNULL,
                    check=False,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
                if result.returncode != 0:
                    return False, "CRL is invalid."
            finally:
                Path(crl_temp.name).unlink(missing_ok=True)

        crl_hash = bytes_hash(crl_file)
        old_hash = JOB.cache_hash(CRL_CACHE_NAME, service_id=first_server)
        crl_path = Path(sep, "var", "cache", "bunkerweb", "mtls", first_server, CRL_CACHE_NAME)
        if old_hash == crl_hash and crl_path.is_file():
            return False, ""

        cached, err = JOB.cache_file(CRL_CACHE_NAME, crl_file, service_id=first_server, checksum=crl_hash, delete_file=False)
        if not cached:
            LOGGER.error(f"Error while caching CRL for {first_server} : {err}")
            return False, err
        return True, ""
    except BaseException as e:
        return False, e


changed = False
failed = False

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
        if _get(first_server, "USE_MTLS", "no") != "yes":
            skipped_servers.append(first_server)
            continue

        verify_mode = _get(first_server, "MTLS_VERIFY_CLIENT", "on")
        ca_priority = _get(first_server, "MTLS_CA_CERTIFICATE_PRIORITY", "file")
        ca_path = _get(first_server, "MTLS_CA_CERTIFICATE")
        ca_data = _get(first_server, "MTLS_CA_CERTIFICATE_DATA")

        if not ca_path and not ca_data:
            if verify_mode != "optional_no_ca":
                LOGGER.warning(
                    f"No client CA bundle configured for {first_server}; mTLS stays disabled for that service "
                    "(set MTLS_CA_CERTIFICATE or MTLS_CA_CERTIFICATE_DATA)"
                )
            else:
                LOGGER.info(f"Service {first_server} runs mTLS with optional_no_ca and no client CA bundle configured")
            skipped_servers.append(first_server)
            continue

        use_file = ca_priority == "file" and ca_path
        ca_file = process_pem_data(ca_data if not use_file else "", ca_path if use_file else None, "CA", first_server)
        if not ca_file:
            if verify_mode != "optional_no_ca":
                LOGGER.warning(f"No valid client CA bundle for {first_server}; mTLS stays disabled for that service")
                failed = True
            skipped_servers.append(first_server)
            continue

        LOGGER.info(f"Checking client CA bundle for {first_server} ...")
        need_reload, err = check_ca(ca_file, first_server)
        if isinstance(err, BaseException):
            LOGGER.error(f"Exception while checking {first_server}'s client CA bundle, skipping ... \n{err}")
            skipped_servers.append(first_server)
            failed = True
            continue
        elif err:
            if verify_mode != "optional_no_ca":
                LOGGER.warning(f"Error while checking {first_server}'s client CA bundle : {err} mTLS stays disabled for that service")
            else:
                LOGGER.warning(f"Error while checking {first_server}'s client CA bundle : {err}")
            skipped_servers.append(first_server)
            failed = True
            continue
        elif need_reload:
            LOGGER.info(f"Detected change in {first_server}'s client CA bundle")
            changed = True
        else:
            LOGGER.info(f"No change in {first_server}'s client CA bundle")

        crl_priority = _get(first_server, "MTLS_CRL_PRIORITY", "file")
        crl_path = _get(first_server, "MTLS_CRL")
        crl_data = _get(first_server, "MTLS_CRL_DATA")

        if not crl_path and not crl_data:
            JOB.del_cache(CRL_CACHE_NAME, service_id=first_server)
            continue

        use_file = crl_priority == "file" and crl_path
        crl_file = process_pem_data(crl_data if not use_file else "", crl_path if use_file else None, "CRL", first_server)
        if not crl_file:
            LOGGER.warning(f"No valid CRL for {first_server}, ignoring")
            JOB.del_cache(CRL_CACHE_NAME, service_id=first_server)
            failed = True
            continue

        LOGGER.info(f"Checking CRL for {first_server} ...")
        need_reload, err = check_crl(crl_file, first_server)
        if isinstance(err, BaseException):
            LOGGER.error(f"Exception while checking {first_server}'s CRL, skipping ... \n{err}")
            failed = True
            continue
        elif err:
            LOGGER.warning(f"Error while checking {first_server}'s CRL : {err}")
            failed = True
            continue
        elif need_reload:
            LOGGER.info(f"Detected change in {first_server}'s CRL")
            changed = True
            continue

        LOGGER.info(f"No change in {first_server}'s CRL")

    for first_server in skipped_servers:
        JOB.del_cache(CA_CACHE_NAME, service_id=first_server)
        JOB.del_cache(CRL_CACHE_NAME, service_id=first_server)

    status = 1 if changed else (2 if failed else 0)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 1 if changed else 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running client-cert.py :\n{e}")

sys_exit(status)
