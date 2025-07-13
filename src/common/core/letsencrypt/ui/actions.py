# -*- coding: utf-8 -*-

from io import BytesIO
from os import sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from sys import path as sys_path
from tarfile import open as tar_open
from typing import Tuple
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module for Let's Encrypt UI actions
logger = setup_logger(
    title="letsencrypt-ui-actions",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-ui-actions")

# Extract cached certificate files from compressed archives.
# Processes tarball cache files and extracts to specified directory.
def extract_cache(folder_path, cache_files):
    logger.debug(f"Extracting cache to folder: {folder_path}")
    logger.debug(f"Processing {len(cache_files)} cache files")
    
    folder_path.mkdir(parents=True, exist_ok=True)
    logger.debug("Created cache extraction directory")

    extracted_count = 0
    for cache_file in cache_files:
        filename = cache_file["file_name"]
        logger.debug(f"Processing cache file: {filename}")
        
        if filename.endswith(".tgz") and filename.startswith("folder:"):
            logger.debug(f"Extracting tarball: {filename}")
            
            try:
                with tar_open(fileobj=BytesIO(cache_file["data"]), mode="r:gz") as tar:
                    try:
                        tar.extractall(folder_path, filter="fully_trusted")
                        logger.debug("Used fully_trusted filter for extraction")
                    except TypeError:
                        tar.extractall(folder_path)
                        logger.debug("Used fallback extraction without filter")
                    
                    extracted_count += 1
                    logger.debug(f"Successfully extracted {filename}")
            except Exception as e:
                logger.exception(f"Failed to extract cache file: {filename}")
                logger.error(f"Extraction error details: {e}")
    
    logger.debug(f"Completed cache extraction - {extracted_count} files processed")

# Retrieve detailed certificate information from certificate files.
# Parses PEM certificates and renewal configurations for UI display.
def retrieve_certificates_info(folder_paths: Tuple[Path, Path]) -> dict:
    logger.debug(f"Retrieving certificate info from {len(folder_paths)} folders")
    
    certificates = {
        "domain": [],
        "common_name": [],
        "issuer": [],
        "issuer_server": [],
        "valid_from": [],
        "valid_to": [],
        "serial_number": [],
        "fingerprint": [],
        "version": [],
        "challenge": [],
        "authenticator": [],
        "key_type": [],
    }

    total_certificates = 0
    for i, folder_path in enumerate(folder_paths):
        logger.debug(f"Processing folder {i+1}/{len(folder_paths)}: {folder_path}")
        
        live_path = folder_path.joinpath("live")
        if not live_path.exists():
            logger.debug(f"Live certificates directory not found: {live_path}")
            continue
        
        cert_files = list(live_path.glob("*/fullchain.pem"))
        logger.debug(f"Found {len(cert_files)} certificate files in {live_path}")
        
        for cert_file in cert_files:
            domain = cert_file.parent.name
            logger.debug(f"Processing certificate for domain: {domain}")
            certificates["domain"].append(domain)

            # Default values for certificate information
            cert_info = {
                "common_name": "Unknown",
                "issuer": "Unknown",
                "issuer_server": "Unknown",
                "valid_from": None,
                "valid_to": None,
                "serial_number": "Unknown",
                "fingerprint": "Unknown",
                "version": "Unknown",
                "preferred_profile": "classic",
                "challenge": "Unknown",
                "authenticator": "Unknown",
                "key_type": "Unknown",
            }

            # * Parsing the certificate file for detailed information
            try:
                logger.debug(f"Reading certificate file: {cert_file}")
                cert_data = cert_file.read_bytes()
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
                logger.debug(f"Successfully loaded certificate for {domain}")

                # ? Getting the subject common name
                subject = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                if subject:
                    cert_info["common_name"] = subject[0].value
                    logger.debug(f"Certificate CN: {cert_info['common_name']}")

                # ? Getting the issuer information
                issuer = cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                if issuer:
                    cert_info["issuer"] = issuer[0].value
                    logger.debug(f"Certificate issuer: {cert_info['issuer']}")

                # ? Getting the validity period
                cert_info["valid_from"] = cert.not_valid_before.strftime("%d-%m-%Y %H:%M:%S UTC")
                cert_info["valid_to"] = cert.not_valid_after.strftime("%d-%m-%Y %H:%M:%S UTC")
                logger.debug(f"Certificate validity: {cert_info['valid_from']} to {cert_info['valid_to']}")

                # ? Getting the serial number
                cert_info["serial_number"] = str(cert.serial_number)
                logger.debug(f"Certificate serial: {cert_info['serial_number']}")

                # ? Getting the SHA256 fingerprint
                fingerprint = cert.fingerprint(hashes.SHA256()).hex()
                cert_info["fingerprint"] = fingerprint
                logger.debug(f"Certificate fingerprint: {fingerprint[:16]}...")

                # ? Getting the certificate version
                cert_info["version"] = cert.version.name
                logger.debug(f"Certificate version: {cert_info['version']}")
                
            except Exception as e:
                logger.exception(f"Error while parsing certificate {cert_file}")
                logger.error(f"Certificate parse error details: {e}")

            # * Parsing the renewal configuration file
            try:
                renewal_file = folder_path.joinpath("renewal", f"{domain}.conf")
                logger.debug(f"Reading renewal config: {renewal_file}")
                
                if renewal_file.exists():
                    logger.debug("Renewal configuration file found")
                    config_lines_processed = 0
                    
                    with renewal_file.open("r") as f:
                        for line in f:
                            line = line.strip()
                            config_lines_processed += 1
                            
                            if line.startswith("preferred_profile = "):
                                cert_info["preferred_profile"] = line.split(" = ")[1].strip()
                                logger.debug(f"Found profile: {cert_info['preferred_profile']}")
                            elif line.startswith("pref_challs = "):
                                cert_info["challenge"] = line.split(" = ")[1].strip().split(",")[0]
                                logger.debug(f"Found challenge: {cert_info['challenge']}")
                            elif line.startswith("authenticator = "):
                                cert_info["authenticator"] = line.split(" = ")[1].strip()
                                logger.debug(f"Found authenticator: {cert_info['authenticator']}")
                            elif line.startswith("server = "):
                                cert_info["issuer_server"] = line.split(" = ")[1].strip()
                                logger.debug(f"Found server: {cert_info['issuer_server']}")
                            elif line.startswith("key_type = "):
                                cert_info["key_type"] = line.split(" = ")[1].strip()
                                logger.debug(f"Found key type: {cert_info['key_type']}")
                    
                    logger.debug(f"Processed {config_lines_processed} lines from renewal config")
                else:
                    logger.debug("No renewal configuration file found")
                    
            except Exception as e:
                logger.exception(f"Error while parsing renewal configuration {renewal_file}")
                logger.error(f"Renewal config parse error details: {e}")

            # Append all certificate information to the results
            for key in cert_info:
                certificates[key].append(cert_info[key])
            
            total_certificates += 1
            logger.debug(f"Completed processing certificate {total_certificates} for domain {domain}")

    logger.debug(f"Certificate info retrieval completed - {total_certificates} certificates processed")
    return certificates

# Prepare certificate data for UI rendering.
# Main entry point for Let's Encrypt certificate management UI.
def pre_render(app, *args, **kwargs):
    logger.debug("Starting pre_render for Let's Encrypt UI")
    logger.info("Preparing Let's Encrypt certificate data for UI display")
    
    ret = {
        "list_certificates": {
            "data": {
                "domain": [],
                "common_name": [],
                "issuer": [],
                "issuer_server": [],
                "valid_from": [],
                "valid_to": [],
                "serial_number": [],
                "fingerprint": [],
                "version": [],
                "preferred_profile": [],
                "challenge": [],
                "authenticator": [],
                "key_type": [],
            },
            "order": {
                "column": 5,
                "dir": "asc",
            },
            "svg_color": "primary",
            "col-size": "col-12",
        },
    }

    # Setup temporary directory for certificate processing
    root_folder = Path(sep, "var", "tmp", "bunkerweb", "ui")
    folder_path = None
    
    try:
        logger.debug("Fetching Let's Encrypt cache files from database")
        # ? Fetching Let's Encrypt cache files
        regular_cache_files = kwargs["db"].get_jobs_cache_files(job_name="certbot-renew")
        logger.debug(f"Retrieved {len(regular_cache_files)} cache files from certbot-renew job")

        # ? Extracting cache files to temporary directory
        folder_path = root_folder.joinpath("letsencrypt", str(uuid4()))
        regular_le_folder = folder_path.joinpath("regular")
        logger.debug(f"Using temporary extraction path: {regular_le_folder}")
        
        extract_cache(regular_le_folder, regular_cache_files)

        # ? Retrieve certificate information by parsing PEM files and configs
        logger.debug("Starting certificate information retrieval")
        cert_data = retrieve_certificates_info((regular_le_folder,))
        ret["list_certificates"]["data"] = cert_data
        
        cert_count = len(cert_data.get("domain", []))
        logger.info(f"Successfully processed {cert_count} Let's Encrypt certificates for UI")
        logger.debug("Certificate data preparation completed successfully")
        
    except Exception as e:
        logger.exception("Failed to get Let's Encrypt certificates for UI")
        logger.error(f"UI certificate processing error details: {e}")
        ret["error"] = str(e)
    finally:
        # Clean up temporary extraction directory
        if folder_path and root_folder.exists():
            logger.debug(f"Cleaning up temporary directory: {root_folder}")
            try:
                rmtree(root_folder, ignore_errors=True)
                logger.debug("Temporary directory cleanup completed")
            except Exception as e:
                logger.debug(f"Cleanup warning - could not remove temp dir: {e}")

    logger.debug("pre_render completed for Let's Encrypt UI")
    return ret
