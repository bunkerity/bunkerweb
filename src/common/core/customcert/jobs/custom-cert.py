#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from tempfile import NamedTemporaryFile
from typing import Tuple, Union, Optional, Literal

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="custom-cert",
    log_file_path="/var/log/bunkerweb/custom-cert.log"
)

logger.debug("Debug mode enabled for custom-cert")

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore

JOB = Job(logger, __file__)


# Process SSL certificate or key data from file path or direct data (base64 or plain text).
def process_ssl_data(data: str, file_path: Optional[str], data_type: Literal["cert", "key"], server_name: str) -> Union[bytes, Path, None]:
    logger.debug(f"process_ssl_data() called for {data_type} on server {server_name}")
    logger.debug(f"Input: file_path={file_path is not None}, data_length={len(data) if data else 0}")
    try:
        if file_path:
            logger.debug(f"Processing {data_type} from file path: {file_path}")
            path_obj = Path(file_path)
            if not path_obj.is_file():
                logger.error(f"{data_type.capitalize()} file {file_path} is not a valid file for {server_name}")
                return None
            logger.debug(f"Valid {data_type} file found: {file_path}, size: {path_obj.stat().st_size} bytes")
            return path_obj

        if not data:
            logger.debug(f"No {data_type} data provided for {server_name}")
            return None

        logger.debug(f"Processing {data_type} from data string (length: {len(data)})")
        # Try base64 decode first
        try:
            decoded = b64decode(data)
            logger.debug(f"Successfully decoded {data_type} as base64 for {server_name}, size: {len(decoded)} bytes")
            return decoded
        except BaseException:
            logger.debug(f"Failed to decode {data_type} data as base64 for server {server_name}, trying as plain text")

            # Try using the data directly as plain text
            try:
                text_data = data.encode()
                # Quick validation check
                if data_type == "cert" and not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                    logger.error(f"Invalid certificate format for server {server_name}")
                    return None
                elif data_type == "key" and (not text_data.strip().startswith(b"-----BEGIN") or not (b"PRIVATE KEY" in text_data)):
                    logger.error(f"Invalid key format for server {server_name}")
                    return None
                logger.debug(f"Successfully processed {data_type} as plain text for {server_name}")
                return text_data
            except BaseException:
                logger.exception(f"Error while processing {data_type} data for server {server_name}")
                return None
    except BaseException as e:
        logger.exception(f"Error processing {data_type} for {server_name}")
        return None


# Validate and cache SSL certificate and key files.
def check_cert(cert_file: Union[Path, bytes], key_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    logger.debug(f"check_cert() called for server {first_server}")
    try:
        ret = False
        if not cert_file or not key_file:
            logger.error("Both cert and key must be provided")
            return False, "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"

        if isinstance(cert_file, Path):
            if not cert_file.is_file():
                logger.error(f"Certificate file {cert_file} is not valid")
                return False, f"Certificate file {cert_file} is not a valid file, ignoring the custom certificate"
            cert_file = cert_file.read_bytes()
            logger.debug(f"Read certificate file, size: {len(cert_file)} bytes")

        if isinstance(key_file, Path):
            if not key_file.is_file():
                logger.error(f"Key file {key_file} is not valid")
                return False, f"Key file {key_file} is not a valid file, ignoring the custom certificate"
            key_file = key_file.read_bytes()
            logger.debug(f"Read key file, size: {len(key_file)} bytes")

        # Write to temporary files for OpenSSL validation
        logger.debug("Creating temporary files for OpenSSL validation")
        with NamedTemporaryFile(delete=False) as cert_temp, NamedTemporaryFile(delete=False) as key_temp:
            try:
                cert_temp.write(cert_file)
                key_temp.write(key_file)
                cert_temp.flush()
                key_temp.flush()
                logger.debug(f"Created temp files: cert={cert_temp.name}, key={key_temp.name}")

                # Validate the certificate using OpenSSL
                logger.debug("Validating certificate with OpenSSL")
                result = run(
                    ["openssl", "x509", "-checkend", "86400", "-noout", "-in", cert_temp.name],
                    stdin=DEVNULL,
                    stderr=DEVNULL,
                    check=False,
                )
                logger.debug(f"OpenSSL validation result: {result.returncode}")

                if result.returncode != 0:
                    logger.warning("Certificate validation failed or expires within 24 hours")
                    return False, "Certificate is invalid or will expire within the next 24 hours."
            finally:
                # Clean up temporary files
                Path(cert_temp.name).unlink(missing_ok=True)
                Path(key_temp.name).unlink(missing_ok=True)
                logger.debug("Cleaned up temporary files")

        logger.debug("Checking certificate hash for changes")
        cert_hash = bytes_hash(cert_file)
        old_hash = JOB.cache_hash("cert.pem", service_id=first_server)
        logger.debug(f"Certificate hash: {cert_hash}, old hash: {old_hash}")
        
        if old_hash != cert_hash:
            ret = True
            logger.debug("Certificate hash changed, caching new certificate")
            cached, err = JOB.cache_file("cert.pem", cert_file, service_id=first_server, checksum=cert_hash, delete_file=False)
            if not cached:
                logger.error(f"Error while caching custom-cert cert.pem file : {err}")
                return False, err

        logger.debug("Checking key hash for changes")
        key_hash = bytes_hash(key_file)
        old_hash = JOB.cache_hash("key.pem", service_id=first_server)
        logger.debug(f"Key hash: {key_hash}, old hash: {old_hash}")
        
        if old_hash != key_hash:
            ret = True
            logger.debug("Key hash changed, caching new key")
            cached, err = JOB.cache_file("key.pem", key_file, service_id=first_server, checksum=key_hash, delete_file=False)
            if not cached:
                logger.error(f"Error while caching custom-key key.pem file : {err}")
                return False, err

        logger.debug(f"Certificate check completed, reload needed: {ret}")
        return ret, ""
    except BaseException as e:
        logger.exception(f"Exception during certificate check for {first_server}")
        return False, e


status = 0

try:
    logger.debug("Starting custom certificate processing")
    
    all_domains = getenv("SERVER_NAME", "www.example.com") or []
    multisite = getenv("MULTISITE", "no") == "yes"
    logger.debug(f"Domains: {all_domains}, multisite: {multisite}")

    if isinstance(all_domains, str):
        all_domains = all_domains.split(" ")

    if not all_domains:
        logger.info("No services found, exiting ...")
        sys_exit(0)

    skipped_servers = []
    if not multisite:
        all_domains = [all_domains[0]]
        if getenv("USE_CUSTOM_SSL", "no") == "no":
            logger.info("Custom SSL is not enabled, skipping ...")
            skipped_servers = all_domains

    if not skipped_servers:
        logger.debug(f"Processing {len(all_domains)} domains for custom SSL")
        for first_server in all_domains:
            logger.debug(f"Checking custom SSL for server: {first_server}")
            
            ssl_enabled = (getenv(f"{first_server}_USE_CUSTOM_SSL", "no") if multisite else getenv("USE_CUSTOM_SSL", "no"))
            if ssl_enabled == "no":
                logger.debug(f"Custom SSL disabled for {first_server}")
                skipped_servers.append(first_server)
                continue

            logger.info(f"Service {first_server} is using custom SSL certificates, checking ...")

            cert_priority = getenv(f"{first_server}_CUSTOM_SSL_CERT_PRIORITY", "file") if multisite else getenv("CUSTOM_SSL_CERT_PRIORITY", "file")
            cert_file_path = getenv(f"{first_server}_CUSTOM_SSL_CERT", "") if multisite else getenv("CUSTOM_SSL_CERT", "")
            key_file_path = getenv(f"{first_server}_CUSTOM_SSL_KEY", "") if multisite else getenv("CUSTOM_SSL_KEY", "")
            cert_data = getenv(f"{first_server}_CUSTOM_SSL_CERT_DATA", "") if multisite else getenv("CUSTOM_SSL_CERT_DATA", "")
            key_data = getenv(f"{first_server}_CUSTOM_SSL_KEY_DATA", "") if multisite else getenv("CUSTOM_SSL_KEY_DATA", "")

            logger.debug(f"SSL config for {first_server}: priority={cert_priority}, file_path_set={bool(cert_file_path)}, data_set={bool(cert_data)}")

            # Use file or data based on priority
            use_cert_file = cert_priority == "file" and cert_file_path
            use_key_file = cert_priority == "file" and key_file_path

            cert_file = process_ssl_data(cert_data if not use_cert_file else "", cert_file_path if use_cert_file else None, "cert", first_server)

            key_file = process_ssl_data(key_data if not use_key_file else "", key_file_path if use_key_file else None, "key", first_server)

            if not cert_file or not key_file:
                logger.warning(
                    "Variables (CUSTOM_SSL_CERT or CUSTOM_SSL_CERT_DATA) and (CUSTOM_SSL_KEY or CUSTOM_SSL_KEY_DATA) "
                    f"have to be set and valid to use custom certificates for {first_server}"
                )
                skipped_servers.append(first_server)
                status = 2
                continue

            logger.info(f"Checking certificate for {first_server} ...")
            need_reload, err = check_cert(cert_file, key_file, first_server)
            if isinstance(err, BaseException):
                logger.error(f"Exception while checking {first_server}'s certificate, skipping ... \n{err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            elif err:
                logger.warning(f"Error while checking {first_server}'s certificate : {err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            elif need_reload:
                logger.info(f"Detected change in {first_server}'s certificate")
                status = 1
                continue

            logger.info(f"No change in {first_server}'s certificate")

    logger.debug(f"Cleaning up cache for {len(skipped_servers)} skipped servers")
    for first_server in skipped_servers:
        JOB.del_cache("cert.pem", service_id=first_server)
        JOB.del_cache("key.pem", service_id=first_server)
        
    logger.debug("Custom certificate processing completed")
    
except SystemExit as e:
    status = e.code
    logger.debug(f"SystemExit with code: {status}")
except BaseException as e:
    status = 2
    logger.exception("Exception while running custom-cert.py")

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
