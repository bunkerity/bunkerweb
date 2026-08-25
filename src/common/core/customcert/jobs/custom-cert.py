#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from traceback import format_exc
from typing import Tuple, Union, Optional, Literal

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from certificate_utils import certificate_status, parse_certificate  # type: ignore
from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("CUSTOM-CERT")
JOB = Job(LOGGER, __file__)


def process_ssl_data(data: str, file_path: Optional[str], data_type: Literal["cert", "key"], server_name: str) -> Union[bytes, Path, None]:
    """Process SSL certificate or key data from file path or direct data (base64 or plain text)"""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{data_type.capitalize()} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        # If the data already looks like PEM, use it directly.
        text_data = data.encode()
        if text_data.strip().startswith(b"-----BEGIN"):
            if data_type == "cert" and not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                LOGGER.error(f"Invalid certificate format for server {server_name}")
                return None
            if data_type == "key" and b"PRIVATE KEY" not in text_data:
                LOGGER.error(f"Invalid key format for server {server_name}")
                return None
            return text_data

        # Try strict base64 decode. We remove whitespaces and pad if needed.
        decoded = b""
        try:
            base64_data = "".join(data.split())
            base64_data += "=" * (-len(base64_data) % 4)
            decoded = b64decode(base64_data, validate=True)
            if data_type == "cert" and not decoded.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                raise ValueError("decoded certificate data is not PEM")
            if data_type == "key" and (not decoded.strip().startswith(b"-----BEGIN") or b"PRIVATE KEY" not in decoded):
                raise ValueError("decoded key data is not PEM")
            return decoded
        except BaseException:
            LOGGER.debug(format_exc())
            LOGGER.warning(f"Failed to decode {data_type} data as base64 for server {server_name}, trying as plain text")

            # Fallback: validate and use plaintext data.
            try:
                if data_type == "cert" and not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                    LOGGER.error(f"Invalid certificate format for server {server_name}")
                    return None
                elif data_type == "key" and (not text_data.strip().startswith(b"-----BEGIN") or b"PRIVATE KEY" not in text_data):
                    LOGGER.error(f"Invalid key format for server {server_name}")
                    return None
                return text_data
            except BaseException:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Error while processing {data_type} data for server {server_name}")
                return None
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {data_type} for {server_name}: {e}")
        return None


def check_cert(cert_file: Union[Path, bytes], key_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    try:
        ret = False
        if not cert_file or not key_file:
            return False, "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"

        if isinstance(cert_file, Path):
            if not cert_file.is_file():
                return False, f"Certificate file {cert_file} is not a valid file, ignoring the custom certificate"
            cert_file = cert_file.read_bytes()

        if isinstance(key_file, Path):
            if not key_file.is_file():
                return False, f"Key file {key_file} is not a valid file, ignoring the custom certificate"
            key_file = key_file.read_bytes()

        # Validate the pair through the same function the inventory path uses
        # (`db_methods.certificates.create_certificate`), so a certificate supplied by setting
        # is held to the checks as one uploaded through the API. The previous check ran
        # `openssl x509 -noout` on the certificate alone and never looked at the key, so a
        # malformed, encrypted or mismatched key was cached and pushed to every instance, and
        # only failed later in Lua -- where the service silently falls back to the default
        # certificate and the operator's first signal is a browser warning.
        try:
            parsed = parse_certificate(cert_file, key_file)
        except (TypeError, ValueError) as e:
            return False, str(e)

        # Expiry warns and never blocks: refusing a certificate that is currently being served
        # would withdraw it and drop the service to the default one, which is worse than
        # serving expired.
        # Not named `status`: the job body below uses a module-level `status` as its exit code.
        cert_state = certificate_status(parsed["valid_from"], parsed["valid_to"])
        if cert_state != "valid":
            LOGGER.warning(f"{first_server}: custom certificate is {cert_state.replace('_', ' ')} (valid from {parsed['valid_from']} to {parsed['valid_to']})")

        cert_hash = bytes_hash(cert_file)
        old_hash = JOB.cache_hash("cert.pem", service_id=first_server)
        cert_path = Path(sep, "var", "cache", "bunkerweb", "customcert", first_server, "cert.pem")
        if old_hash != cert_hash or not cert_path.is_file():
            ret = True
            cached, err = JOB.cache_file("cert.pem", cert_file, service_id=first_server, checksum=cert_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-cert cert.pem file : {err}")
                return False, err

        key_hash = bytes_hash(key_file)
        old_hash = JOB.cache_hash("key.pem", service_id=first_server)
        key_path = Path(sep, "var", "cache", "bunkerweb", "customcert", first_server, "key.pem")
        if old_hash != key_hash or not key_path.is_file():
            ret = True
            cached, err = JOB.cache_file("key.pem", key_file, service_id=first_server, checksum=key_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-key key.pem file : {err}")
                return False, err

        return ret, ""
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

    skipped_servers = []
    managed_servers = []
    if not multisite:
        all_domains = [all_domains[0]]
        if getenv("USE_CUSTOM_SSL", "no") == "no":
            LOGGER.info("Custom SSL is not enabled, skipping ...")
            skipped_servers = all_domains

    if not skipped_servers:
        for first_server in all_domains:
            if (getenv(f"{first_server}_USE_CUSTOM_SSL", "no") if multisite else getenv("USE_CUSTOM_SSL", "no")) == "no":
                skipped_servers.append(first_server)
                continue

            LOGGER.info(f"Service {first_server} is using custom SSL certificates, checking ...")

            cert_priority = getenv(f"{first_server}_CUSTOM_SSL_CERT_PRIORITY", "file") if multisite else getenv("CUSTOM_SSL_CERT_PRIORITY", "file")
            cert_file_path = getenv(f"{first_server}_CUSTOM_SSL_CERT", "") if multisite else getenv("CUSTOM_SSL_CERT", "")
            key_file_path = getenv(f"{first_server}_CUSTOM_SSL_KEY", "") if multisite else getenv("CUSTOM_SSL_KEY", "")
            cert_data = getenv(f"{first_server}_CUSTOM_SSL_CERT_DATA", "") if multisite else getenv("CUSTOM_SSL_CERT_DATA", "")
            key_data = getenv(f"{first_server}_CUSTOM_SSL_KEY_DATA", "") if multisite else getenv("CUSTOM_SSL_KEY_DATA", "")

            # Use file or data based on priority
            use_cert_file = cert_priority == "file" and cert_file_path
            use_key_file = cert_priority == "file" and key_file_path

            cert_file = process_ssl_data(cert_data if not use_cert_file else "", cert_file_path if use_cert_file else None, "cert", first_server)

            key_file = process_ssl_data(key_data if not use_key_file else "", key_file_path if use_key_file else None, "key", first_server)

            if not cert_file or not key_file:
                LOGGER.warning(
                    "Variables (CUSTOM_SSL_CERT or CUSTOM_SSL_CERT_DATA) and (CUSTOM_SSL_KEY or CUSTOM_SSL_KEY_DATA) "
                    f"have to be set and valid to use custom certificates for {first_server}"
                )
                skipped_servers.append(first_server)
                status = 2
                continue

            LOGGER.info(f"Checking certificate for {first_server} ...")
            need_reload, err = check_cert(cert_file, key_file, first_server)
            if isinstance(err, BaseException):
                LOGGER.error(f"Exception while checking {first_server}'s certificate, skipping ... \n{err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            elif err:
                LOGGER.warning(f"Error while checking {first_server}'s certificate : {err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            # Mirror the material into the central inventory so the certificate is visible and
            # manageable from the certificates page, which this provider has no UI of its own for.
            managed_servers.append(first_server)
            # In the file-priority branch these are still Paths — check_cert() reads them into
            # bytes only inside its own scope — and the inventory API takes PEM bytes.
            import_err, _ = JOB.db.import_certificate(
                name=first_server,
                description="Managed by the custom certificate provider",
                source="customcert",
                certificate_pem=cert_file.read_bytes() if isinstance(cert_file, Path) else cert_file,
                private_key_pem=key_file.read_bytes() if isinstance(key_file, Path) else key_file,
                service_ids=[first_server],
                primary=True,
                renewal_metadata={"managed_by": "customcert"},
            )
            if import_err:
                LOGGER.error(f"Could not add {first_server}'s certificate to the inventory : {import_err}")

            if need_reload:
                LOGGER.info(f"Detected change in {first_server}'s certificate")
                status = 1
                continue

            LOGGER.info(f"No change in {first_server}'s certificate")

    for first_server in skipped_servers:
        JOB.del_cache("cert.pem", service_id=first_server)
        JOB.del_cache("key.pem", service_id=first_server)

    # Services this provider no longer covers must lose their attachment, otherwise the
    # inventory would keep serving a certificate whose setting has just been turned off.
    if sync_err := JOB.db.sync_managed_attachments("customcert", managed_servers):
        LOGGER.error(f"Could not sync the custom certificate attachments : {sync_err}")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running custom-cert.py :\n{e}")

sys_exit(status)
