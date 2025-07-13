from os import getenv, sep
from subprocess import DEVNULL, PIPE, STDOUT, run
from os.path import dirname, join
from pathlib import Path
from shutil import rmtree
from sys import path as sys_path
from io import BytesIO
from tarfile import open as tar_open

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger
from app.dependencies import DB  # type: ignore
from app.routes.utils import cors_required  # type: ignore

# Initialize bw_logger module for Let's Encrypt Flask routes
logger = setup_logger(
    title="letsencrypt-blueprints",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-blueprints")

# Flask blueprint configuration for Let's Encrypt UI routes
blueprint_path = dirname(__file__)
logger.debug(f"Blueprint path: {blueprint_path}")

letsencrypt = Blueprint(
    "letsencrypt",
    __name__,
    static_folder=f"{blueprint_path}/static",
    template_folder=f"{blueprint_path}/templates",
)

# Certificate management paths and binaries
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
LE_CACHE_DIR = join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc")
DATA_PATH = join(sep, "var", "tmp", "bunkerweb", "ui", "letsencrypt", "etc")
WORK_DIR = join(sep, "var", "tmp", "bunkerweb", "ui", "letsencrypt", "lib")
LOGS_DIR = join(sep, "var", "tmp", "bunkerweb", "letsencrypt", "log")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

logger.debug(f"Certificate paths configured - DATA_PATH: {DATA_PATH}, CERTBOT_BIN: {CERTBOT_BIN}")

# Download and extract certificate data from database cache.
# Retrieves cached certificate files for UI display and management.
def download_certificates():
    logger.debug(f"Downloading certificates to: {DATA_PATH}")
    
    # Clean existing data directory
    rmtree(DATA_PATH, ignore_errors=True)
    Path(DATA_PATH).mkdir(parents=True, exist_ok=True)
    logger.debug("Cleaned and recreated certificate data directory")

    # Retrieve certificate cache files from database
    cache_files = DB.get_jobs_cache_files(job_name="certbot-renew")
    logger.debug(f"Retrieved {len(cache_files)} cache files from certbot-renew job")

    extracted_count = 0
    for cache_file in cache_files:
        filename = cache_file["file_name"]
        
        if filename.endswith(".tgz") and filename.startswith("folder:"):
            logger.debug(f"Extracting certificate archive: {filename}")
            
            try:
                with tar_open(fileobj=BytesIO(cache_file["data"]), mode="r:gz") as tar:
                    try:
                        tar.extractall(DATA_PATH, filter="fully_trusted")
                        logger.debug("Used fully_trusted filter for extraction")
                    except TypeError:
                        tar.extractall(DATA_PATH)
                        logger.debug("Used fallback extraction without filter")
                
                extracted_count += 1
                logger.debug(f"Successfully extracted {filename}")
            except Exception as e:
                logger.exception(f"Failed to extract certificate archive: {filename}")
                logger.error(f"Extraction error details: {e}")

    logger.debug(f"Certificate download completed - {extracted_count} archives extracted")

# Retrieve and parse all certificate information for UI display.
# Combines certificate parsing with renewal configuration data.
def retrieve_certificates():
    logger.debug("Starting certificate retrieval process")
    download_certificates()

    # Initialize certificate data structure
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
        "preferred_profile": [],
        "challenge": [],
        "authenticator": [],
        "key_type": [],
    }

    # Find all certificate files in the live directory
    live_path = Path(DATA_PATH).joinpath("live")
    if not live_path.exists():
        logger.debug("No live certificates directory found")
        return certificates
    
    cert_files = list(live_path.glob("*/fullchain.pem"))
    logger.debug(f"Found {len(cert_files)} certificate files to process")

    for cert_file in cert_files:
        domain = cert_file.parent.name
        logger.debug(f"Processing certificate for domain: {domain}")
        certificates["domain"].append(domain)
        
        # Initialize certificate information with defaults
        cert_info = {
            "common_name": domain,
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
        
        # Parse certificate file for detailed information
        try:
            logger.debug(f"Parsing certificate file: {cert_file}")
            cert_data = cert_file.read_bytes()
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            
            # Extract subject common name
            subject = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if subject:
                cert_info["common_name"] = subject[0].value
                logger.debug(f"Certificate CN: {cert_info['common_name']}")
            
            # Extract issuer information
            issuer = cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if issuer:
                cert_info["issuer"] = issuer[0].value
                logger.debug(f"Certificate issuer: {cert_info['issuer']}")
            
            # Extract validity period with timezone information
            cert_info["valid_from"] = cert.not_valid_before.astimezone().isoformat()
            cert_info["valid_to"] = cert.not_valid_after.astimezone().isoformat()
            logger.debug(f"Certificate validity: {cert_info['valid_from']} to {cert_info['valid_to']}")
            
            # Extract serial number and fingerprint
            cert_info["serial_number"] = str(cert.serial_number)
            cert_info["fingerprint"] = cert.fingerprint(hashes.SHA256()).hex()
            cert_info["version"] = cert.version.name
            
            logger.debug(f"Certificate details - Serial: {cert_info['serial_number']}, "
                        f"Fingerprint: {cert_info['fingerprint'][:16]}..., Version: {cert_info['version']}")
            
        except Exception as e:
            logger.exception(f"Error while parsing certificate {cert_file}")
            logger.error(f"Certificate parse error details: {e}")

        # Parse renewal configuration file for additional metadata
        try:
            renewal_file = Path(DATA_PATH).joinpath("renewal", f"{domain}.conf")
            logger.debug(f"Reading renewal configuration: {renewal_file}")
            
            if renewal_file.exists():
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

        # Add certificate information to results
        for key in cert_info:
            certificates[key].append(cert_info[key])

    logger.debug(f"Certificate retrieval completed - {len(certificates['domain'])} certificates processed")
    return certificates

# Main Let's Encrypt management page route.
# Renders the certificate management interface.
@letsencrypt.route("/letsencrypt", methods=["GET"])
@login_required
def letsencrypt_page():
    logger.debug("Rendering Let's Encrypt management page")
    logger.info("User accessed Let's Encrypt certificate management interface")
    return render_template("letsencrypt.html")

# API endpoint to fetch certificate data for DataTables display.
# Returns JSON formatted certificate information for UI tables.
@letsencrypt.route("/letsencrypt/fetch", methods=["POST"])
@login_required
@cors_required
def letsencrypt_fetch():
    logger.debug("Fetching certificate data for UI display")
    cert_list = []

    try:
        # Retrieve and process certificates
        certs = retrieve_certificates()
        logger.debug(f"Retrieved certificate data with {len(certs.get('domain', []))} certificates")
        
        # Format certificate data for DataTables
        for i, domain in enumerate(certs.get("domain", [])):
            cert_data = {
                "domain": domain,
                "common_name": certs.get("common_name", [""])[i],
                "issuer": certs.get("issuer", [""])[i],
                "issuer_server": certs.get("issuer_server", [""])[i],
                "valid_from": certs.get("valid_from", [""])[i],
                "valid_to": certs.get("valid_to", [""])[i],
                "serial_number": certs.get("serial_number", [""])[i],
                "fingerprint": certs.get("fingerprint", [""])[i],
                "version": certs.get("version", [""])[i],
                "preferred_profile": certs.get("preferred_profile", [""])[i],
                "challenge": certs.get("challenge", [""])[i],
                "authenticator": certs.get("authenticator", [""])[i],
                "key_type": certs.get("key_type", [""])[i],
            }
            cert_list.append(cert_data)
            logger.debug(f"Formatted certificate data for domain: {domain}")
        
        logger.info(f"Successfully prepared {len(cert_list)} certificates for UI display")
        
    except Exception as e:
        logger.exception("Error while fetching certificates for UI")
        logger.error(f"Certificate fetch error details: {e}")

    # Return DataTables compatible JSON response
    response_data = {
        "data": cert_list,
        "recordsTotal": len(cert_list),
        "recordsFiltered": len(cert_list),
        "draw": int(request.form.get("draw", 1)),
    }
    
    logger.debug(f"Returning certificate fetch response with {len(cert_list)} records")
    return jsonify(response_data)

# API endpoint to delete a specific certificate.
# Handles certificate deletion and cache updates.
@letsencrypt.route("/letsencrypt/delete", methods=["POST"])
@login_required
@cors_required
def letsencrypt_delete():
    cert_name = request.json.get("cert_name")
    logger.debug(f"Certificate deletion request for: {cert_name}")
    
    if not cert_name:
        logger.error("Certificate deletion failed - missing cert_name parameter")
        return jsonify({"status": "ko", "message": "Missing cert_name"}), 400

    logger.info(f"Starting certificate deletion process for: {cert_name}")

    # Download current certificate data
    download_certificates()

    # Setup environment for certbot execution
    env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
    env["PYTHONPATH"] = env["PYTHONPATH"] + (f":{DEPS_PATH}" if DEPS_PATH not in env["PYTHONPATH"] else "")
    logger.debug("Environment configured for certbot deletion")

    # Execute certbot delete command
    delete_command = [
        CERTBOT_BIN,
        "delete",
        "--config-dir",
        DATA_PATH,
        "--work-dir",
        WORK_DIR,
        "--logs-dir",
        LOGS_DIR,
        "--cert-name",
        cert_name,
        "-n",  # non-interactive
    ]
    
    logger.debug(f"Executing certbot delete command: {' '.join(delete_command)}")
    
    delete_proc = run(
        delete_command,
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        env=env,
        check=False,
    )

    logger.debug(f"Certbot delete completed with return code: {delete_proc.returncode}")

    if delete_proc.returncode == 0:
        logger.info(f"Successfully deleted certificate {cert_name}")
        
        # Clean up certificate files and directories
        cert_dir = Path(DATA_PATH).joinpath("live", cert_name)
        archive_dir = Path(DATA_PATH).joinpath("archive", cert_name)
        renewal_file = Path(DATA_PATH).joinpath("renewal", f"{cert_name}.conf")

        logger.debug("Starting certificate file cleanup")
        
        # Remove certificate directories
        for path in (cert_dir, archive_dir):
            if path.exists():
                try:
                    file_count = 0
                    for file in path.glob("*"):
                        try:
                            file.unlink()
                            file_count += 1
                        except Exception as e:
                            logger.error(f"Failed to remove file {file}: {e}")
                    
                    path.rmdir()
                    logger.info(f"Removed directory {path} with {file_count} files")
                except Exception as e:
                    logger.error(f"Failed to remove directory {path}: {e}")

        # Remove renewal configuration file
        if renewal_file.exists():
            try:
                renewal_file.unlink()
                logger.info(f"Removed renewal file {renewal_file}")
            except Exception as e:
                logger.error(f"Failed to remove renewal file {renewal_file}: {e}")

        # Update cache with modified certificate data
        try:
            logger.debug("Updating certificate cache after deletion")
            dir_path = Path(LE_CACHE_DIR)
            file_name = f"folder:{dir_path.as_posix()}.tgz"
            content = BytesIO()
            
            with tar_open(file_name, mode="w:gz", fileobj=content, compresslevel=9) as tgz:
                tgz.add(DATA_PATH, arcname=".")
            content.seek(0, 0)

            # Update database cache
            err = DB.upsert_job_cache("", file_name, content.getvalue(), job_name="certbot-renew")
            if err:
                logger.error(f"Failed to update certificate cache: {err}")
                return jsonify({"status": "ko", "message": f"Failed to cache letsencrypt dir: {err}"})
            else:
                # Mark changes for processing
                err = DB.checked_changes(["plugins"], ["letsencrypt"], True)
                if err:
                    logger.error(f"Failed to mark certificate changes: {err}")
                    return jsonify({"status": "ko", "message": f"Failed to cache letsencrypt dir: {err}"})
                
                logger.debug("Certificate cache updated successfully")
                
        except Exception as e:
            logger.exception("Failed to update certificate cache after deletion")
            return jsonify({"status": "ok", "message": f"Successfully deleted certificate {cert_name}, but failed to cache letsencrypt dir: {e}"})
        
        logger.info(f"Certificate deletion completed successfully for: {cert_name}")
        return jsonify({"status": "ok", "message": f"Successfully deleted certificate {cert_name}"})
    else:
        logger.error(f"Failed to delete certificate {cert_name}: {delete_proc.stdout}")
        return jsonify({"status": "ko", "message": f"Failed to delete certificate {cert_name}: {delete_proc.stdout}"})

# Static file handler for Let's Encrypt blueprint assets.
# Serves CSS, JS, and other static files for the UI.
@letsencrypt.route("/letsencrypt/<path:filename>")
@login_required
def letsencrypt_static(filename):
    logger.debug(f"Serving static file: {filename}")
    return letsencrypt.send_static_file(filename)

logger.debug("Let's Encrypt Flask blueprint initialized successfully")