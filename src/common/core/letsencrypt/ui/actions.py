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
from cryptography.x509 import oid
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def extract_cache(folder_path, cache_files):
    # Extract Let's Encrypt cache files to specified folder path.
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(logger, f"Starting cache extraction to {folder_path}")
    debug_log(logger, f"Processing {len(cache_files)} cache files")
    debug_log(logger, f"Target folder exists: {folder_path.exists()}")
    
    folder_path.mkdir(parents=True, exist_ok=True)
    
    debug_log(logger, f"Created directory structure: {folder_path}")
    debug_log(logger, 
        f"Directory permissions: {oct(folder_path.stat().st_mode)}")

    extracted_files = 0
    total_bytes = 0
    
    for i, cache_file in enumerate(cache_files):
        file_name = cache_file.get("file_name", "unknown")
        file_data = cache_file.get("data", b"")
        
        debug_log(logger, f"Examining cache file {i+1}/{len(cache_files)}: "
                          f"{file_name}")
        debug_log(logger, f"File size: {len(file_data)} bytes")
        
        if (cache_file["file_name"].endswith(".tgz") and 
                cache_file["file_name"].startswith("folder:")):
            
            debug_log(logger, 
                f"Processing archive: {cache_file['file_name']}")
            debug_log(logger, 
                f"Archive size: {len(cache_file['data'])} bytes")
            
            try:
                with tar_open(fileobj=BytesIO(cache_file["data"]), 
                              mode="r:gz") as tar:
                    
                    members = tar.getmembers()
                    debug_log(logger, 
                        f"Archive contains {len(members)} members")
                    # Show first few members
                    for j, member in enumerate(members[:5]):
                        debug_log(logger, 
                            f"  Member {j+1}: {member.name} "
                            f"({member.size} bytes, "
                            f"{'dir' if member.isdir() else 'file'})")
                    if len(members) > 5:
                        debug_log(logger, 
                            f"  ... and {len(members) - 5} more members")
                    
                    try:
                        tar.extractall(folder_path, filter="fully_trusted")
                        debug_log(logger, 
                            "Extraction completed with fully_trusted filter")
                    except TypeError:
                        # Fallback for older Python versions without filter
                        debug_log(logger, 
                            "Using fallback extraction without filter")
                        tar.extractall(folder_path)
                    
                    extracted_files += 1
                    total_bytes += len(cache_file['data'])
                    
                    debug_log(logger, 
                        f"Successfully extracted {cache_file['file_name']}")
                    debug_log(logger, 
                        f"Extracted {len(members)} items from archive")
                        
            except Exception as e:
                logger.error(f"Failed to extract {cache_file['file_name']}: "
                           f"{e}")
                debug_log(logger, f"Extraction error details: {format_exc()}")
        else:
            debug_log(logger, f"Skipping non-archive file: {file_name}")

    debug_log(logger, "Cache extraction completed:")
    debug_log(logger, f"  - Files processed: {len(cache_files)}")
    debug_log(logger, f"  - Archives extracted: {extracted_files}")
    debug_log(logger, f"  - Total bytes processed: {total_bytes}")
    
    # List final directory contents
    if folder_path.exists():
        all_items = list(folder_path.rglob("*"))
        files = [item for item in all_items if item.is_file()]
        dirs = [item for item in all_items if item.is_dir()]
        
        debug_log(logger, "Final directory structure:")
        debug_log(logger, f"  - Total items: {len(all_items)}")
        debug_log(logger, f"  - Files: {len(files)}")
        debug_log(logger, f"  - Directories: {len(dirs)}")
        
        # Show some example files
        for i, file_item in enumerate(files[:5]):
            rel_path = file_item.relative_to(folder_path)
            debug_log(logger, 
                f"    File {i+1}: {rel_path} "
                f"({file_item.stat().st_size} bytes)")
        if len(files) > 5:
            debug_log(logger, f"    ... and {len(files) - 5} more files")


def retrieve_certificates_info(folder_paths: Tuple[Path, ...]) -> dict:
    # Retrieve comprehensive certificate information from folder paths.
    # 
    # Parses Let's Encrypt certificate files and renewal configurations
    # to extract detailed certificate information including validity dates,
    # issuer information, and configuration details.
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(logger, 
        f"Retrieving certificate info from {len(folder_paths)} folder paths")
    
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
        "ocsp_support": [],
    }

    total_certs_processed = 0
    
    for folder_idx, folder_path in enumerate(folder_paths):
        debug_log(logger, 
            f"Processing folder {folder_idx + 1}/{len(folder_paths)}: "
            f"{folder_path}")
        
        cert_files = list(folder_path.joinpath("live").glob("*/fullchain.pem"))
        
        debug_log(logger, f"Found {len(cert_files)} certificate files in "
                          f"{folder_path}")
        
        for cert_file in cert_files:
            domain = cert_file.parent.name
            certificates["domain"].append(domain)
            total_certs_processed += 1
            
            debug_log(logger, 
                f"Processing certificate {total_certs_processed}: {domain}")

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
                "ocsp_support": "Unknown",
            }

            # Parse the certificate file
            try:
                debug_log(logger, 
                    f"Loading X.509 certificate from {cert_file}")
                debug_log(logger, 
                    f"Certificate file size: {cert_file.stat().st_size} bytes")
                
                cert_bytes = cert_file.read_bytes()
                debug_log(logger, 
                    f"Read {len(cert_bytes)} bytes from certificate file")
                debug_log(logger, 
                    f"Certificate data preview: {cert_bytes[:100]}...")
                
                cert = x509.load_pem_x509_certificate(
                    cert_bytes, default_backend()
                )
                
                debug_log(logger, 
                    f"Successfully loaded certificate for {domain}")
                debug_log(logger, f"Certificate version: {cert.version}")
                debug_log(logger, f"Certificate serial: {cert.serial_number}")

                # Extract subject (Common Name)
                subject = cert.subject.get_attributes_for_oid(
                    x509.NameOID.COMMON_NAME
                )
                if subject:
                    cert_info["common_name"] = subject[0].value
                    debug_log(logger, 
                        f"Certificate CN: {cert_info['common_name']}")
                else:
                    debug_log(logger, 
                        "No Common Name found in certificate subject")
                    debug_log(logger, f"Full subject: {cert.subject}")

                # Extract issuer (Certificate Authority)
                issuer = cert.issuer.get_attributes_for_oid(
                    x509.NameOID.COMMON_NAME
                )
                if issuer:
                    cert_info["issuer"] = issuer[0].value
                    debug_log(logger, 
                        f"Certificate issuer: {cert_info['issuer']}")
                else:
                    debug_log(logger, 
                        "No Common Name found in certificate issuer")
                    debug_log(logger, f"Full issuer: {cert.issuer}")

                # Extract validity period
                cert_info["valid_from"] = (
                    cert.not_valid_before.strftime("%d-%m-%Y %H:%M:%S UTC")
                )
                cert_info["valid_to"] = (
                    cert.not_valid_after.strftime("%d-%m-%Y %H:%M:%S UTC")
                )
                
                debug_log(logger, 
                    f"Certificate validity: {cert_info['valid_from']} to "
                    f"{cert_info['valid_to']}")
                # Check if certificate is currently valid
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                is_valid = (cert.not_valid_before <= now <= 
                           cert.not_valid_after)
                debug_log(logger, f"Certificate currently valid: {is_valid}")

                # Extract serial number
                cert_info["serial_number"] = str(cert.serial_number)

                # Calculate fingerprint
                fingerprint_bytes = cert.fingerprint(hashes.SHA256())
                cert_info["fingerprint"] = fingerprint_bytes.hex()
                
                debug_log(logger, 
                    f"Certificate fingerprint: {cert_info['fingerprint']}")

                # Extract version
                cert_info["version"] = cert.version.name
                
                # Check for OCSP support via Authority Information Access ext
                try:
                    aia_ext = cert.extensions.get_extension_for_oid(
                        oid.ExtensionOID.AUTHORITY_INFORMATION_ACCESS
                    )
                    ocsp_urls = []
                    for access_description in aia_ext.value:
                        if (access_description.access_method == 
                                oid.AuthorityInformationAccessOID.OCSP):
                            ocsp_urls.append(
                                str(access_description.access_location.value)
                            )
                    
                    if ocsp_urls:
                        cert_info["ocsp_support"] = "Yes"
                        debug_log(logger, 
                            f"OCSP URLs found for {domain}: {ocsp_urls}")
                    else:
                        cert_info["ocsp_support"] = "No"
                        debug_log(logger, 
                            f"AIA extension found for {domain} but no OCSP URLs")
                            
                except x509.ExtensionNotFound:
                    cert_info["ocsp_support"] = "No"
                    debug_log(logger, 
                        f"No Authority Information Access extension found for "
                        f"{domain}")
                except Exception as ocsp_error:
                    cert_info["ocsp_support"] = "Unknown"
                    debug_log(logger, 
                        f"Error checking OCSP support for {domain}: "
                        f"{ocsp_error}")
                
                debug_log(logger, 
                    f"Certificate processing completed for {domain}")
                debug_log(logger, f"  - Serial: {cert_info['serial_number']}")
                debug_log(logger, f"  - Version: {cert_info['version']}")
                debug_log(logger, f"  - Subject: {cert_info['common_name']}")
                debug_log(logger, f"  - Issuer: {cert_info['issuer']}")
                debug_log(logger, 
                    f"  - OCSP Support: {cert_info['ocsp_support']}")
                
            except BaseException as e:
                error_msg = (f"Error while parsing certificate {cert_file}: "
                           f"{e}")
                logger.error(error_msg)
                debug_log(logger, "Certificate parsing error details:")
                debug_log(logger, f"  - Error type: {type(e).__name__}")
                debug_log(logger, f"  - Error message: {str(e)}")
                debug_log(logger, f"  - Full traceback: {format_exc()}")
                debug_log(logger, f"  - Certificate file: {cert_file}")
                debug_log(logger, f"  - File exists: {cert_file.exists()}")
                debug_log(logger, f"  - File readable: {cert_file.is_file()}")

            # Parse the renewal configuration file
            try:
                renewal_file = folder_path.joinpath("renewal", 
                                                   f"{domain}.conf")
                
                if renewal_file.exists():
                    debug_log(logger, 
                        f"Processing renewal configuration: {renewal_file}")
                    
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
                    
                    debug_log(logger, 
                        f"Renewal config parsed - Profile: "
                        f"{cert_info['preferred_profile']}, "
                        f"Challenge: {cert_info['challenge']}, "
                        f"Key type: {cert_info['key_type']}")
                else:
                    debug_log(logger, 
                        f"No renewal configuration found for {domain}")
                        
            except BaseException as e:
                error_msg = (f"Error while parsing renewal configuration "
                           f"{renewal_file}: {e}")
                logger.error(error_msg)
                debug_log(logger, f"Renewal config parsing error: "
                                  f"{format_exc()}")

            # Append all certificate information to the results
            for key in cert_info:
                certificates[key].append(cert_info[key])

    debug_log(logger, 
        f"Certificate retrieval complete. Processed "
        f"{total_certs_processed} certificates from {len(folder_paths)} "
        f"folders")
    
    # Summary of OCSP support
    ocsp_support_counts = {"Yes": 0, "No": 0, "Unknown": 0}
    for ocsp_status in certificates.get('ocsp_support', []):
        ocsp_support_counts[ocsp_status] = (
            ocsp_support_counts.get(ocsp_status, 0) + 1
        )
    debug_log(logger, f"OCSP support summary: {ocsp_support_counts}")

    return certificates


def pre_render(app, *args, **kwargs):
    # Pre-render function to prepare Let's Encrypt certificate data for UI.
    # 
    # Retrieves certificate information from database cache files and
    # prepares the data structure for rendering in the web interface.
    # Handles extraction of cache files, certificate parsing, and error
    # handling for the certificate management interface.
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(logger, "Starting pre-render for Let's Encrypt certificates")
    
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
                "ocsp_support": [],
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
        debug_log(logger, "Starting Let's Encrypt data retrieval process")
        debug_log(logger, f"Database connection available: {'db' in kwargs}")
        debug_log(logger, f"Root folder: {root_folder}")
        
        # Retrieve cache files from database
        debug_log(logger, 
            "Fetching cache files from database for job: certbot-renew")
        
        regular_cache_files = kwargs["db"].get_jobs_cache_files(
            job_name="certbot-renew"
        )
        
        debug_log(logger, f"Retrieved {len(regular_cache_files)} cache files")
        for i, cache_file in enumerate(regular_cache_files):
            file_name = cache_file.get("file_name", "unknown")
            file_size = len(cache_file.get("data", b""))
            debug_log(logger, 
                f"  Cache file {i+1}: {file_name} ({file_size} bytes)")

        # Create unique temporary folder for extraction
        folder_uuid = str(uuid4())
        folder_path = root_folder.joinpath("letsencrypt", folder_uuid)
        regular_le_folder = folder_path.joinpath("regular")
        
        debug_log(logger, f"Using temporary folder UUID: {folder_uuid}")
        debug_log(logger, f"Temporary folder path: {folder_path}")
        debug_log(logger, f"Regular LE folder: {regular_le_folder}")

        # Extract cache files to temporary location
        debug_log(logger, "Starting cache file extraction")
        
        extract_cache(regular_le_folder, regular_cache_files)
        
        debug_log(logger, 
            "Cache extraction completed, starting certificate parsing")

        # Parse certificates and retrieve information
        cert_data = retrieve_certificates_info((regular_le_folder,))
        
        cert_count = len(cert_data.get("domain", []))
        
        debug_log(logger, "Certificate parsing completed")
        debug_log(logger, f"Total certificates processed: {cert_count}")
        debug_log(logger, f"Certificate data keys: {list(cert_data.keys())}")
        
        # Log sample certificate data (first certificate if available)
        if cert_count > 0:
            debug_log(logger, 
                "Sample certificate data (first certificate):")
            for key in cert_data:
                value = cert_data[key][0] if cert_data[key] else "None"
                if key == "ocsp_support":
                    debug_log(logger, 
                        f"  {key}: {value} (OCSP support detected)")
                else:
                    debug_log(logger, f"  {key}: {value}")
        
        ret["list_certificates"]["data"] = cert_data
        
        logger.info(f"Pre-render completed successfully with {cert_count} "
                   f"certificates")
        
        debug_log(logger, f"Return data structure keys: {list(ret.keys())}")
        debug_log(logger, 
            f"Certificate list structure: "
            f"{list(ret['list_certificates'].keys())}")
        
    except BaseException as e:
        error_msg = f"Failed to get Let's Encrypt certificates: {e}"
        logger.error(error_msg)
        
        debug_log(logger, "Pre-render error occurred:")
        debug_log(logger, f"  - Error type: {type(e).__name__}")
        debug_log(logger, f"  - Error message: {str(e)}")
        debug_log(logger, f"  - Error traceback: {format_exc()}")
        debug_log(logger, 
            f"  - kwargs keys: {list(kwargs.keys()) if kwargs else 'None'}")
        if "db" in kwargs:
            debug_log(logger, 
                f"  - Database object type: {type(kwargs['db'])}")
        
        ret["error"] = {"message": str(e)}
        
    finally:
        # Clean up temporary files
        if folder_path and folder_path.exists():
            try:
                debug_log(logger, 
                    f"Cleaning up temporary folder: {root_folder}")
                
                rmtree(root_folder, ignore_errors=True)
                
                debug_log(logger, "Temporary folder cleanup completed")
                    
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary folder "
                             f"{root_folder}: {cleanup_error}")

    debug_log(logger, "Pre-render function completed")

    return ret