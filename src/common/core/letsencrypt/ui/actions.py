from io import BytesIO
from logging import getLogger
from os import getenv
from os.path import sep
from pathlib import Path
from shutil import rmtree
from tarfile import open as tar_open
from traceback import format_exc
from typing import Tuple
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


def extract_cache(folder_path, cache_files):
    # Extract Let's Encrypt cache files to specified folder path.
    # 
    # Args:
    #     folder_path (Path): Destination folder path for extraction
    #     cache_files (list): List of cache file dictionaries containing
    #                        file data to extract
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        logger.debug(f"Starting cache extraction to {folder_path}")
        logger.debug(f"Processing {len(cache_files)} cache files")
        logger.debug(f"Target folder exists: {folder_path.exists()}")
    
    folder_path.mkdir(parents=True, exist_ok=True)
    
    if is_debug:
        logger.debug(f"Created directory structure: {folder_path}")
        logger.debug(f"Directory permissions: {oct(folder_path.stat().st_mode)}")

    extracted_files = 0
    total_bytes = 0
    
    for i, cache_file in enumerate(cache_files):
        file_name = cache_file.get("file_name", "unknown")
        file_data = cache_file.get("data", b"")
        
        if is_debug:
            logger.debug(f"Examining cache file {i+1}/{len(cache_files)}: {file_name}")
            logger.debug(f"File size: {len(file_data)} bytes")
        
        if (cache_file["file_name"].endswith(".tgz") and 
                cache_file["file_name"].startswith("folder:")):
            
            if is_debug:
                logger.debug(f"Processing archive: {cache_file['file_name']}")
                logger.debug(f"Archive size: {len(cache_file['data'])} bytes")
            
            try:
                with tar_open(fileobj=BytesIO(cache_file["data"]), 
                              mode="r:gz") as tar:
                    
                    members = tar.getmembers()
                    if is_debug:
                        logger.debug(f"Archive contains {len(members)} members")
                        # Show first few members
                        for j, member in enumerate(members[:5]):
                            logger.debug(f"  Member {j+1}: {member.name} "
                                       f"({member.size} bytes, "
                                       f"{'dir' if member.isdir() else 'file'})")
                        if len(members) > 5:
                            logger.debug(f"  ... and {len(members) - 5} more members")
                    
                    try:
                        tar.extractall(folder_path, filter="fully_trusted")
                        if is_debug:
                            logger.debug("Extraction completed with fully_trusted filter")
                    except TypeError:
                        # Fallback for older Python versions without filter
                        if is_debug:
                            logger.debug("Using fallback extraction without filter")
                        tar.extractall(folder_path)
                    
                    extracted_files += 1
                    total_bytes += len(cache_file['data'])
                    
                    if is_debug:
                        logger.debug(f"Successfully extracted {cache_file['file_name']}")
                        logger.debug(f"Extracted {len(members)} items from archive")
                        
            except Exception as e:
                logger.error(f"Failed to extract {cache_file['file_name']}: {e}")
                if is_debug:
                    logger.debug(f"Extraction error details: {format_exc()}")
        else:
            if is_debug:
                logger.debug(f"Skipping non-archive file: {file_name}")

    if is_debug:
        logger.debug(f"Cache extraction completed:")
        logger.debug(f"  - Files processed: {len(cache_files)}")
        logger.debug(f"  - Archives extracted: {extracted_files}")
        logger.debug(f"  - Total bytes processed: {total_bytes}")
        
        # List final directory contents
        if folder_path.exists():
            all_items = list(folder_path.rglob("*"))
            files = [item for item in all_items if item.is_file()]
            dirs = [item for item in all_items if item.is_dir()]
            
            logger.debug(f"Final directory structure:")
            logger.debug(f"  - Total items: {len(all_items)}")
            logger.debug(f"  - Files: {len(files)}")
            logger.debug(f"  - Directories: {len(dirs)}")
            
            # Show some example files
            for i, file_item in enumerate(files[:5]):
                rel_path = file_item.relative_to(folder_path)
                logger.debug(f"    File {i+1}: {rel_path} ({file_item.stat().st_size} bytes)")
            if len(files) > 5:
                logger.debug(f"    ... and {len(files) - 5} more files")


def retrieve_certificates_info(folder_paths: Tuple[Path, ...]) -> dict:
    # Retrieve comprehensive certificate information from folder paths.
    # 
    # Parses Let's Encrypt certificate files and renewal configurations
    # to extract detailed certificate information including validity dates,
    # issuer information, and configuration details.
    # 
    # Args:
    #     folder_paths (Tuple[Path, ...]): Tuple of folder paths containing
    #                                     certificate data to process
    #                                     
    # Returns:
    #     dict: Dictionary containing lists of certificate information
    #           with keys for domain, common_name, issuer, validity dates,
    #           and other certificate metadata
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        logger.debug(f"Retrieving certificate info from {len(folder_paths)} "
                    f"folder paths")
    
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

    total_certs_processed = 0
    
    for folder_idx, folder_path in enumerate(folder_paths):
        if is_debug:
            logger.debug(f"Processing folder {folder_idx + 1}/{len(folder_paths)}: "
                        f"{folder_path}")
        
        cert_files = list(folder_path.joinpath("live").glob("*/fullchain.pem"))
        
        if is_debug:
            logger.debug(f"Found {len(cert_files)} certificate files in "
                        f"{folder_path}")
        
        for cert_file in cert_files:
            domain = cert_file.parent.name
            certificates["domain"].append(domain)
            total_certs_processed += 1
            
            if is_debug:
                logger.debug(f"Processing certificate {total_certs_processed}: "
                            f"{domain}")

            # Initialize default certificate information
            cert_info = {
                "common_name": "Unknown",
                "issuer": "Unknown",
                "issuer_server": "Unknown",
                "valid_from": None,
                "valid_to": None,
                "serial_number": "Unknown",
                "fingerprint": "Unknown",
                "version": "Unknown",
                "preferred_profile": "Unknown",
                "challenge": "Unknown",
                "authenticator": "Unknown",
                "key_type": "Unknown",
            }

            # Parse the certificate file
            try:
                if is_debug:
                    logger.debug(f"Loading X.509 certificate from {cert_file}")
                    logger.debug(f"Certificate file size: {cert_file.stat().st_size} bytes")
                
                cert_bytes = cert_file.read_bytes()
                if is_debug:
                    logger.debug(f"Read {len(cert_bytes)} bytes from certificate file")
                    logger.debug(f"Certificate data preview: {cert_bytes[:100]}...")
                
                cert = x509.load_pem_x509_certificate(
                    cert_bytes, default_backend()
                )
                
                if is_debug:
                    logger.debug(f"Successfully loaded certificate for {domain}")
                    logger.debug(f"Certificate version: {cert.version}")
                    logger.debug(f"Certificate serial: {cert.serial_number}")

                # Extract subject (Common Name)
                subject = cert.subject.get_attributes_for_oid(
                    x509.NameOID.COMMON_NAME
                )
                if subject:
                    cert_info["common_name"] = subject[0].value
                    if is_debug:
                        logger.debug(f"Certificate CN: {cert_info['common_name']}")
                else:
                    if is_debug:
                        logger.debug("No Common Name found in certificate subject")
                        logger.debug(f"Full subject: {cert.subject}")

                # Extract issuer (Certificate Authority)
                issuer = cert.issuer.get_attributes_for_oid(
                    x509.NameOID.COMMON_NAME
                )
                if issuer:
                    cert_info["issuer"] = issuer[0].value
                    if is_debug:
                        logger.debug(f"Certificate issuer: {cert_info['issuer']}")
                else:
                    if is_debug:
                        logger.debug("No Common Name found in certificate issuer")
                        logger.debug(f"Full issuer: {cert.issuer}")

                # Extract validity period
                cert_info["valid_from"] = (
                    cert.not_valid_before.strftime("%d-%m-%Y %H:%M:%S UTC")
                )
                cert_info["valid_to"] = (
                    cert.not_valid_after.strftime("%d-%m-%Y %H:%M:%S UTC")
                )
                
                if is_debug:
                    logger.debug(f"Certificate validity: {cert_info['valid_from']} "
                                f"to {cert_info['valid_to']}")
                    # Check if certificate is currently valid
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    is_valid = cert.not_valid_before <= now <= cert.not_valid_after
                    logger.debug(f"Certificate currently valid: {is_valid}")

                # Extract serial number
                cert_info["serial_number"] = str(cert.serial_number)

                # Calculate fingerprint
                fingerprint_bytes = cert.fingerprint(hashes.SHA256())
                cert_info["fingerprint"] = fingerprint_bytes.hex()
                
                if is_debug:
                    logger.debug(f"Certificate fingerprint: {cert_info['fingerprint']}")

                # Extract version
                cert_info["version"] = cert.version.name
                
                if is_debug:
                    logger.debug(f"Certificate processing completed for {domain}")
                    logger.debug(f"  - Serial: {cert_info['serial_number']}")
                    logger.debug(f"  - Version: {cert_info['version']}")
                    logger.debug(f"  - Subject: {cert_info['common_name']}")
                    logger.debug(f"  - Issuer: {cert_info['issuer']}")
                
            except BaseException as e:
                error_msg = f"Error while parsing certificate {cert_file}: {e}"
                logger.error(error_msg)
                if is_debug:
                    logger.debug(f"Certificate parsing error details:")
                    logger.debug(f"  - Error type: {type(e).__name__}")
                    logger.debug(f"  - Error message: {str(e)}")
                    logger.debug(f"  - Full traceback: {format_exc()}")
                    logger.debug(f"  - Certificate file: {cert_file}")
                    logger.debug(f"  - File exists: {cert_file.exists()}")
                    logger.debug(f"  - File readable: {cert_file.is_file()}")

            # Parse the renewal configuration file
            try:
                renewal_file = folder_path.joinpath("renewal", f"{domain}.conf")
                
                if renewal_file.exists():
                    if is_debug:
                        logger.debug(f"Processing renewal configuration: "
                                    f"{renewal_file}")
                    
                    with renewal_file.open("r") as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                                
                            if line.startswith("preferred_profile = "):
                                cert_info["preferred_profile"] = (
                                    line.split(" = ")[1].strip()
                                )
                            elif line.startswith("pref_challs = "):
                                # Take first challenge from comma-separated list
                                challenges = line.split(" = ")[1].strip()
                                cert_info["challenge"] = challenges.split(",")[0]
                            elif line.startswith("authenticator = "):
                                cert_info["authenticator"] = (
                                    line.split(" = ")[1].strip()
                                )
                            elif line.startswith("server = "):
                                cert_info["issuer_server"] = (
                                    line.split(" = ")[1].strip()
                                )
                            elif line.startswith("key_type = "):
                                cert_info["key_type"] = (
                                    line.split(" = ")[1].strip()
                                )
                    
                    if is_debug:
                        logger.debug(f"Renewal config parsed - Profile: "
                                    f"{cert_info['preferred_profile']}, "
                                    f"Challenge: {cert_info['challenge']}, "
                                    f"Key type: {cert_info['key_type']}")
                else:
                    if is_debug:
                        logger.debug(f"No renewal configuration found for "
                                    f"{domain}")
                        
            except BaseException as e:
                error_msg = (f"Error while parsing renewal configuration "
                           f"{renewal_file}: {e}")
                logger.error(error_msg)
                if is_debug:
                    logger.debug(f"Renewal config parsing error: {format_exc()}")

            # Append all certificate information to the results
            for key in cert_info:
                certificates[key].append(cert_info[key])

    if is_debug:
        logger.debug(f"Certificate retrieval complete. Processed "
                    f"{total_certs_processed} certificates from "
                    f"{len(folder_paths)} folders")

    return certificates


def pre_render(app, *args, **kwargs):
    # Pre-render function to prepare Let's Encrypt certificate data for UI.
    # 
    # Retrieves certificate information from database cache files and
    # prepares the data structure for rendering in the web interface.
    # Handles extraction of cache files, certificate parsing, and error
    # handling for the certificate management interface.
    # 
    # Args:
    #     app: Flask application instance
    #     *args: Variable length argument list
    #     **kwargs: Keyword arguments containing database connection and
    #              other configuration options
    #              
    # Returns:
    #     dict: Dictionary containing certificate data, display configuration,
    #           and any error information for the UI template
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        logger.debug("Starting pre-render for Let's Encrypt certificates")
    
    # Initialize return structure with default values
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

    root_folder = Path(sep, "var", "tmp", "bunkerweb", "ui")
    folder_path = None
    
    try:
        if is_debug:
            logger.debug("Starting Let's Encrypt data retrieval process")
            logger.debug(f"Database connection available: {'db' in kwargs}")
            logger.debug(f"Root folder: {root_folder}")
        
        # Retrieve cache files from database
        if is_debug:
            logger.debug("Fetching cache files from database for job: certbot-renew")
        
        regular_cache_files = kwargs["db"].get_jobs_cache_files(
            job_name="certbot-renew"
        )
        
        if is_debug:
            logger.debug(f"Retrieved {len(regular_cache_files)} cache files")
            for i, cache_file in enumerate(regular_cache_files):
                file_name = cache_file.get("file_name", "unknown")
                file_size = len(cache_file.get("data", b""))
                logger.debug(f"  Cache file {i+1}: {file_name} ({file_size} bytes)")

        # Create unique temporary folder for extraction
        folder_uuid = str(uuid4())
        folder_path = root_folder.joinpath("letsencrypt", folder_uuid)
        regular_le_folder = folder_path.joinpath("regular")
        
        if is_debug:
            logger.debug(f"Using temporary folder UUID: {folder_uuid}")
            logger.debug(f"Temporary folder path: {folder_path}")
            logger.debug(f"Regular LE folder: {regular_le_folder}")

        # Extract cache files to temporary location
        if is_debug:
            logger.debug("Starting cache file extraction")
        
        extract_cache(regular_le_folder, regular_cache_files)
        
        if is_debug:
            logger.debug("Cache extraction completed, starting certificate parsing")

        # Parse certificates and retrieve information
        cert_data = retrieve_certificates_info((regular_le_folder,))
        
        cert_count = len(cert_data.get("domain", []))
        
        if is_debug:
            logger.debug(f"Certificate parsing completed")
            logger.debug(f"Total certificates processed: {cert_count}")
            logger.debug(f"Certificate data keys: {list(cert_data.keys())}")
            
            # Log sample certificate data (first certificate if available)
            if cert_count > 0:
                logger.debug("Sample certificate data (first certificate):")
                for key in cert_data:
                    value = cert_data[key][0] if cert_data[key] else "None"
                    logger.debug(f"  {key}: {value}")
        
        ret["list_certificates"]["data"] = cert_data
        
        logger.info(f"Pre-render completed successfully with {cert_count} "
                   f"certificates")
        
        if is_debug:
            logger.debug(f"Return data structure keys: {list(ret.keys())}")
            logger.debug(f"Certificate list structure: {list(ret['list_certificates'].keys())}")
        
    except BaseException as e:
        error_msg = f"Failed to get Let's Encrypt certificates: {e}"
        logger.error(error_msg)
        
        if is_debug:
            logger.debug(f"Pre-render error occurred:")
            logger.debug(f"  - Error type: {type(e).__name__}")
            logger.debug(f"  - Error message: {str(e)}")
            logger.debug(f"  - Error traceback: {format_exc()}")
            logger.debug(f"  - kwargs keys: {list(kwargs.keys()) if kwargs else 'None'}")
            if "db" in kwargs:
                logger.debug(f"  - Database object type: {type(kwargs['db'])}")
        
        ret["error"] = str(e)
        
    finally:
        # Clean up temporary files
        if folder_path and folder_path.exists():
            try:
                if is_debug:
                    logger.debug(f"Cleaning up temporary folder: {root_folder}")
                
                rmtree(root_folder, ignore_errors=True)
                
                if is_debug:
                    logger.debug("Temporary folder cleanup completed")
                    
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary folder "
                             f"{root_folder}: {cleanup_error}")

    if is_debug:
        logger.debug("Pre-render function completed")

    return ret