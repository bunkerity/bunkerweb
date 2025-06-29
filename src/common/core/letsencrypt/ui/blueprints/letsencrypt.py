from os import getenv
from subprocess import DEVNULL, PIPE, STDOUT, run
from os.path import dirname, join, sep
from pathlib import Path
from shutil import rmtree
from io import BytesIO
from tarfile import open as tar_open
from traceback import format_exc

from cryptography import x509
from cryptography.x509 import oid
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

from app.dependencies import DB  # type: ignore
from app.utils import LOGGER  # type: ignore
from app.routes.utils import cors_required  # type: ignore

blueprint_path = dirname(__file__)

letsencrypt = Blueprint(
    "letsencrypt",
    __name__,
    static_folder=f"{blueprint_path}/static",
    template_folder=f"{blueprint_path}/templates",
)

CERTBOT_BIN = join(
    sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot"
)
LE_CACHE_DIR = join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc")
DATA_PATH = join(sep, "var", "tmp", "bunkerweb", "ui", "letsencrypt", "etc")
WORK_DIR = join(sep, "var", "tmp", "bunkerweb", "ui", "letsencrypt", "lib")
LOGS_DIR = join(sep, "var", "tmp", "bunkerweb", "letsencrypt", "log")

DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")


def download_certificates():
    # Download and extract Let's Encrypt certificates from database cache.
    # 
    # Retrieves certificate cache files from the database and extracts them
    # to the local data path for processing.
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        LOGGER.debug(f"Starting certificate download process")
        LOGGER.debug(f"Target directory: {DATA_PATH}")
        LOGGER.debug(f"Cache directory: {LE_CACHE_DIR}")
    
    # Clean up and create fresh directory
    if Path(DATA_PATH).exists():
        if is_debug:
            LOGGER.debug(f"Removing existing directory: {DATA_PATH}")
        rmtree(DATA_PATH, ignore_errors=True)
    
    if is_debug:
        LOGGER.debug(f"Creating directory structure: {DATA_PATH}")
    Path(DATA_PATH).mkdir(parents=True, exist_ok=True)

    if is_debug:
        LOGGER.debug("Fetching cache files from database")
    cache_files = DB.get_jobs_cache_files(job_name="certbot-renew")
    
    if is_debug:
        LOGGER.debug(f"Retrieved {len(cache_files)} cache files")
        for i, cache_file in enumerate(cache_files):
            LOGGER.debug(f"Cache file {i+1}: {cache_file['file_name']} "
                        f"({len(cache_file.get('data', b''))} bytes)")

    extracted_count = 0
    for cache_file in cache_files:
        if (cache_file["file_name"].endswith(".tgz") and 
                cache_file["file_name"].startswith("folder:")):
            
            if is_debug:
                LOGGER.debug(f"Extracting cache file: "
                           f"{cache_file['file_name']}")
                LOGGER.debug(f"File size: {len(cache_file['data'])} bytes")
            
            try:
                with tar_open(fileobj=BytesIO(cache_file["data"]), 
                              mode="r:gz") as tar:
                    member_count = len(tar.getmembers())
                    if is_debug:
                        LOGGER.debug(f"Archive contains {member_count} "
                                    f"members")
                    
                    try:
                        tar.extractall(DATA_PATH, filter="fully_trusted")
                        if is_debug:
                            LOGGER.debug("Extraction completed with "
                                        "fully_trusted filter")
                    except TypeError:
                        if is_debug:
                            LOGGER.debug("Falling back to extraction without "
                                        "filter")
                        tar.extractall(DATA_PATH)
                    
                    extracted_count += 1
                    if is_debug:
                        LOGGER.debug(f"Successfully extracted "
                                    f"{cache_file['file_name']}")
                        
            except Exception as e:
                LOGGER.error(f"Failed to extract {cache_file['file_name']}: "
                           f"{e}")
                if is_debug:
                    LOGGER.debug(f"Extraction error details: {format_exc()}")
        else:
            if is_debug:
                LOGGER.debug(f"Skipping non-matching file: "
                           f"{cache_file['file_name']}")

    if is_debug:
        LOGGER.debug(f"Certificate download completed: {extracted_count} "
                    f"files extracted")
        # List extracted directory contents
        if Path(DATA_PATH).exists():
            contents = list(Path(DATA_PATH).rglob("*"))
            LOGGER.debug(f"Extracted directory contains {len(contents)} "
                        f"items")
            for item in contents[:10]:  # Show first 10 items
                LOGGER.debug(f"  - {item}")
            if len(contents) > 10:
                LOGGER.debug(f"  ... and {len(contents) - 10} more items")


def retrieve_certificates():
    # Retrieve and parse Let's Encrypt certificate information.
    # 
    # Downloads certificates from cache and parses both the certificate
    # files and renewal configuration to extract comprehensive certificate
    # information.
    # 
    # Returns:
    #     dict: Dictionary containing lists of certificate information
    #           including domain, issuer, validity dates, etc.
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        LOGGER.debug("Starting certificate retrieval")
    
    download_certificates()

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
        "ocsp_support": [],
    }

    cert_files = list(Path(DATA_PATH).joinpath("live").glob("*/fullchain.pem"))
    
    if is_debug:
        LOGGER.debug(f"Processing {len(cert_files)} certificate files")

    for cert_file in cert_files:
        domain = cert_file.parent.name
        certificates["domain"].append(domain)
        
        if is_debug:
            LOGGER.debug(f"Processing certificate "
                        f"{len(certificates['domain'])}: {domain}")
            LOGGER.debug(f"Certificate file path: {cert_file}")
            LOGGER.debug(f"Certificate file size: "
                        f"{cert_file.stat().st_size} bytes")
        
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
        
        try:
            if is_debug:
                LOGGER.debug(f"Loading X.509 certificate from {cert_file}")
            
            cert_data = cert_file.read_bytes()
            if is_debug:
                LOGGER.debug(f"Certificate data length: {len(cert_data)} "
                           f"bytes")
                LOGGER.debug(f"Certificate starts with: {cert_data[:50]}")
            
            cert = x509.load_pem_x509_certificate(
                cert_data, default_backend()
            )
            
            if is_debug:
                LOGGER.debug(f"Successfully loaded certificate for {domain}")
                LOGGER.debug(f"Certificate subject: {cert.subject}")
                LOGGER.debug(f"Certificate issuer: {cert.issuer}")
            
            subject = cert.subject.get_attributes_for_oid(
                x509.NameOID.COMMON_NAME
            )
            if subject:
                cert_info["common_name"] = subject[0].value
                if is_debug:
                    LOGGER.debug(f"Certificate CN extracted: "
                               f"{cert_info['common_name']}")
            else:
                if is_debug:
                    LOGGER.debug("No Common Name found in certificate "
                                "subject")
            
            issuer = cert.issuer.get_attributes_for_oid(
                x509.NameOID.COMMON_NAME
            )
            if issuer:
                cert_info["issuer"] = issuer[0].value
                if is_debug:
                    LOGGER.debug(f"Certificate issuer extracted: "
                               f"{cert_info['issuer']}")
            else:
                if is_debug:
                    LOGGER.debug("No Common Name found in certificate "
                                "issuer")
            
            cert_info["valid_from"] = (
                cert.not_valid_before.astimezone().isoformat()
            )
            cert_info["valid_to"] = (
                cert.not_valid_after.astimezone().isoformat()
            )
            
            if is_debug:
                LOGGER.debug(f"Certificate validity period: "
                           f"{cert_info['valid_from']} to "
                           f"{cert_info['valid_to']}")
            
            cert_info["serial_number"] = str(cert.serial_number)
            cert_info["fingerprint"] = cert.fingerprint(hashes.SHA256()).hex()
            cert_info["version"] = cert.version.name
            
            # Check for OCSP support via Authority Information Access extension
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
                    if is_debug:
                        LOGGER.debug(f"OCSP URLs found: {ocsp_urls}")
                else:
                    cert_info["ocsp_support"] = "No"
                    if is_debug:
                        LOGGER.debug("AIA extension found but no OCSP URLs")
                        
            except x509.ExtensionNotFound:
                cert_info["ocsp_support"] = "No"
                if is_debug:
                    LOGGER.debug("No Authority Information Access extension "
                                "found")
            except Exception as ocsp_error:
                cert_info["ocsp_support"] = "Unknown"
                if is_debug:
                    LOGGER.debug(f"Error checking OCSP support: "
                               f"{ocsp_error}")
            
            if is_debug:
                LOGGER.debug(f"Certificate details extracted:")
                LOGGER.debug(f"  - Serial: {cert_info['serial_number']}")
                LOGGER.debug(f"  - Fingerprint: "
                           f"{cert_info['fingerprint'][:16]}...")
                LOGGER.debug(f"  - Version: {cert_info['version']}")
                LOGGER.debug(f"  - OCSP Support: {cert_info['ocsp_support']}")
            
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while parsing certificate {cert_file}: {e}")
            if is_debug:
                LOGGER.debug(f"Certificate parsing failed for {domain}: "
                           f"{str(e)}")
                LOGGER.debug(f"Error type: {type(e).__name__}")

        try:
            renewal_file = Path(DATA_PATH).joinpath("renewal", 
                                                   f"{domain}.conf")
            if renewal_file.exists():
                if is_debug:
                    LOGGER.debug(f"Processing renewal file: {renewal_file}")
                    LOGGER.debug(f"Renewal file size: "
                                f"{renewal_file.stat().st_size} bytes")
                
                config_lines_processed = 0
                with renewal_file.open("r") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                            
                        config_lines_processed += 1
                        if is_debug and line_num <= 10:  # Debug first 10 lines
                            LOGGER.debug(f"Renewal config line {line_num}: "
                                       f"{line}")
                        
                        if line.startswith("preferred_profile = "):
                            cert_info["preferred_profile"] = (
                                line.split(" = ")[1].strip()
                            )
                            if is_debug:
                                LOGGER.debug(f"Found preferred_profile: "
                                           f"{cert_info['preferred_profile']}")
                        elif line.startswith("pref_challs = "):
                            challenges = line.split(" = ")[1].strip()
                            cert_info["challenge"] = challenges.split(",")[0]
                            if is_debug:
                                LOGGER.debug(f"Found challenge: "
                                           f"{cert_info['challenge']} "
                                           f"(from {challenges})")
                        elif line.startswith("authenticator = "):
                            cert_info["authenticator"] = (
                                line.split(" = ")[1].strip()
                            )
                            if is_debug:
                                LOGGER.debug(f"Found authenticator: "
                                           f"{cert_info['authenticator']}")
                        elif line.startswith("server = "):
                            cert_info["issuer_server"] = (
                                line.split(" = ")[1].strip()
                            )
                            if is_debug:
                                LOGGER.debug(f"Found issuer_server: "
                                           f"{cert_info['issuer_server']}")
                        elif line.startswith("key_type = "):
                            cert_info["key_type"] = (
                                line.split(" = ")[1].strip()
                            )
                            if is_debug:
                                LOGGER.debug(f"Found key_type: "
                                           f"{cert_info['key_type']}")
                
                if is_debug:
                    LOGGER.debug(f"Processed {config_lines_processed} "
                                f"configuration lines")
                    LOGGER.debug(f"Final renewal configuration for {domain}:")
                    LOGGER.debug(f"  - Profile: "
                                f"{cert_info['preferred_profile']}")
                    LOGGER.debug(f"  - Challenge: {cert_info['challenge']}")
                    LOGGER.debug(f"  - Authenticator: "
                                f"{cert_info['authenticator']}")
                    LOGGER.debug(f"  - Server: {cert_info['issuer_server']}")
                    LOGGER.debug(f"  - Key type: {cert_info['key_type']}")
            else:
                if is_debug:
                    LOGGER.debug(f"No renewal file found for {domain} at "
                                f"{renewal_file}")
                    
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while parsing renewal configuration "
                        f"{renewal_file}: {e}")
            if is_debug:
                LOGGER.debug(f"Renewal config parsing failed for {domain}: "
                           f"{str(e)}")
                LOGGER.debug(f"Error type: {type(e).__name__}")

        for key in cert_info:
            certificates[key].append(cert_info[key])

    if is_debug:
        LOGGER.debug(f"Retrieved {len(certificates['domain'])} certificates")
        # Summary of OCSP support
        ocsp_support_counts = {"Yes": 0, "No": 0, "Unknown": 0}
        for ocsp_status in certificates.get('ocsp_support', []):
            ocsp_support_counts[ocsp_status] = (
                ocsp_support_counts.get(ocsp_status, 0) + 1
            )
        LOGGER.debug(f"OCSP support summary: {ocsp_support_counts}")

    return certificates


@letsencrypt.route("/letsencrypt", methods=["GET"])
@login_required
def letsencrypt_page():
    # Render the Let's Encrypt certificates management page.
    # 
    # Returns:
    #     str: Rendered HTML template for the Let's Encrypt page
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        LOGGER.debug("Rendering Let's Encrypt page")
    
    return render_template("letsencrypt.html")


@letsencrypt.route("/letsencrypt/fetch", methods=["POST"])
@login_required
@cors_required
def letsencrypt_fetch():
    # Fetch certificate data for DataTables AJAX requests.
    # 
    # Retrieves and formats certificate information for display in the
    # DataTables interface.
    # 
    # Returns:
    #     dict: JSON response containing certificate data, record counts,
    #           and draw number for DataTables
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        LOGGER.debug("Fetching certificates for DataTables")
    
    cert_list = []

    try:
        certs = retrieve_certificates()
        
        if is_debug:
            LOGGER.debug(f"Retrieved certificates: "
                        f"{len(certs.get('domain', []))}")
        
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
                "ocsp_support": certs.get("ocsp_support", [""])[i],
            }
            cert_list.append(cert_data)
            
            if is_debug:
                LOGGER.debug(f"Added certificate to list: {domain}")
                LOGGER.debug(f"  - OCSP Support: "
                           f"{cert_data['ocsp_support']}")
                LOGGER.debug(f"  - Challenge: {cert_data['challenge']}")
                LOGGER.debug(f"  - Key Type: {cert_data['key_type']}")
                
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while fetching certificates: {e}")

    response_data = {
        "data": cert_list,
        "recordsTotal": len(cert_list),
        "recordsFiltered": len(cert_list),
        "draw": int(request.form.get("draw", 1)),
    }
    
    if is_debug:
        LOGGER.debug(f"Returning {len(cert_list)} certificates to "
                    f"DataTables")

    return jsonify(response_data)


@letsencrypt.route("/letsencrypt/delete", methods=["POST"])
@login_required
@cors_required
def letsencrypt_delete():
    # Delete a Let's Encrypt certificate.
    # 
    # Removes the specified certificate using certbot and cleans up
    # associated files and directories. Updates the database cache
    # with the modified certificate data.
    # 
    # Returns:
    #     dict: JSON response indicating success or failure of the
    #           deletion operation
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    cert_name = request.json.get("cert_name")
    if not cert_name:
        if is_debug:
            LOGGER.debug("Certificate deletion request missing cert_name")
        return jsonify({"status": "ko", "message": "Missing cert_name"}), 400

    if is_debug:
        LOGGER.debug(f"Starting deletion of certificate: {cert_name}")

    download_certificates()

    env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
    env["PYTHONPATH"] = env["PYTHONPATH"] + (
        f":{DEPS_PATH}" if DEPS_PATH not in env["PYTHONPATH"] else ""
    )

    if is_debug:
        LOGGER.debug(f"Running certbot delete for {cert_name}")
        LOGGER.debug(f"Environment: PATH={env['PATH'][:100]}...")
        LOGGER.debug(f"PYTHONPATH: {env['PYTHONPATH'][:100]}...")

    delete_proc = run(
        [
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
        ],
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        env=env,
        check=False,
    )

    if is_debug:
        LOGGER.debug(f"Certbot delete return code: {delete_proc.returncode}")
        if delete_proc.stdout:
            LOGGER.debug(f"Certbot output: {delete_proc.stdout}")

    if delete_proc.returncode == 0:
        LOGGER.info(f"Successfully deleted certificate {cert_name}")
        
        # Clean up certificate directories and files
        cert_dir = Path(DATA_PATH).joinpath("live", cert_name)
        archive_dir = Path(DATA_PATH).joinpath("archive", cert_name)
        renewal_file = Path(DATA_PATH).joinpath("renewal", 
                                               f"{cert_name}.conf")

        if is_debug:
            LOGGER.debug(f"Cleaning up directories for {cert_name}")

        for path in (cert_dir, archive_dir):
            if path.exists():
                try:
                    for file in path.glob("*"):
                        try:
                            file.unlink()
                            if is_debug:
                                LOGGER.debug(f"Removed file: {file}")
                        except Exception as e:
                            LOGGER.error(f"Failed to remove file {file}: "
                                       f"{e}")
                    path.rmdir()
                    LOGGER.info(f"Removed directory {path}")
                except Exception as e:
                    LOGGER.error(f"Failed to remove directory {path}: {e}")

        if renewal_file.exists():
            try:
                renewal_file.unlink()
                LOGGER.info(f"Removed renewal file {renewal_file}")
                if is_debug:
                    LOGGER.debug(f"Renewal file removed: {renewal_file}")
            except Exception as e:
                LOGGER.error(f"Failed to remove renewal file "
                           f"{renewal_file}: {e}")

        # Update database cache with modified certificate data
        try:
            if is_debug:
                LOGGER.debug("Updating database cache with modified data")
            
            dir_path = Path(LE_CACHE_DIR)
            file_name = f"folder:{dir_path.as_posix()}.tgz"
            content = BytesIO()
            
            with tar_open(file_name, mode="w:gz", fileobj=content, 
                         compresslevel=9) as tgz:
                tgz.add(DATA_PATH, arcname=".")
            
            content.seek(0, 0)

            err = DB.upsert_job_cache("", file_name, content.getvalue(), 
                                    job_name="certbot-renew")
            if err:
                return jsonify({"status": "ko", 
                              "message": f"Failed to cache letsencrypt "
                                       f"dir: {err}"})
            else:
                err = DB.checked_changes(["plugins"], ["letsencrypt"], True)
                if err:
                    return jsonify({"status": "ko", 
                                  "message": f"Failed to cache letsencrypt "
                                           f"dir: {err}"})
                    
            if is_debug:
                LOGGER.debug("Database cache updated successfully")
                
        except Exception as e:
            error_msg = (f"Successfully deleted certificate {cert_name}, "
                        f"but failed to cache letsencrypt dir: {e}")
            LOGGER.error(error_msg)
            return jsonify({"status": "ok", "message": error_msg})
            
        return jsonify({"status": "ok", 
                       "message": f"Successfully deleted certificate "
                                f"{cert_name}"})
    else:
        error_msg = (f"Failed to delete certificate {cert_name}: "
                    f"{delete_proc.stdout}")
        LOGGER.error(error_msg)
        return jsonify({"status": "ko", "message": error_msg})


@letsencrypt.route("/letsencrypt/<path:filename>")
@login_required
def letsencrypt_static(filename):
    # Serve static files for the Let's Encrypt blueprint.
    # 
    # Args:
    #     filename (str): Path to the static file to serve
    #         
    # Returns:
    #     Response: Flask response object for the static file
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        LOGGER.debug(f"Serving static file: {filename}")
    
    return letsencrypt.send_static_file(filename)