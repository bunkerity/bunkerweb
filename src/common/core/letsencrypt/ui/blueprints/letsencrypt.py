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


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def download_certificates():
    # Download and extract Let's Encrypt certificates from database cache.
    # 
    # Retrieves certificate cache files from the database and extracts them
    # to the local data path for processing.
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(LOGGER, "Starting certificate download process")
    debug_log(LOGGER, f"Target directory: {DATA_PATH}")
    debug_log(LOGGER, f"Cache directory: {LE_CACHE_DIR}")
    
    # Clean up and create fresh directory
    if Path(DATA_PATH).exists():
        debug_log(LOGGER, f"Removing existing directory: {DATA_PATH}")
        rmtree(DATA_PATH, ignore_errors=True)
    
    debug_log(LOGGER, f"Creating directory structure: {DATA_PATH}")
    Path(DATA_PATH).mkdir(parents=True, exist_ok=True)

    debug_log(LOGGER, "Fetching cache files from database")
    cache_files = DB.get_jobs_cache_files(job_name="certbot-renew")
    
    debug_log(LOGGER, f"Retrieved {len(cache_files)} cache files")
    for i, cache_file in enumerate(cache_files):
        debug_log(LOGGER, f"Cache file {i+1}: {cache_file['file_name']} "
                          f"({len(cache_file.get('data', b''))} bytes)")

    extracted_count = 0
    for cache_file in cache_files:
        if (cache_file["file_name"].endswith(".tgz") and 
                cache_file["file_name"].startswith("folder:")):
            
            debug_log(LOGGER, 
                f"Extracting cache file: {cache_file['file_name']}")
            debug_log(LOGGER, f"File size: {len(cache_file['data'])} bytes")
            
            try:
                with tar_open(fileobj=BytesIO(cache_file["data"]), 
                              mode="r:gz") as tar:
                    member_count = len(tar.getmembers())
                    debug_log(LOGGER, 
                        f"Archive contains {member_count} members")
                    
                    try:
                        tar.extractall(DATA_PATH, filter="fully_trusted")
                        debug_log(LOGGER, 
                            "Extraction completed with fully_trusted filter")
                    except TypeError:
                        debug_log(LOGGER, 
                            "Falling back to extraction without filter")
                        tar.extractall(DATA_PATH)
                    
                    extracted_count += 1
                    debug_log(LOGGER, 
                        f"Successfully extracted {cache_file['file_name']}")
                        
            except Exception as e:
                LOGGER.error(f"Failed to extract {cache_file['file_name']}: "
                           f"{e}")
                debug_log(LOGGER, f"Extraction error details: {format_exc()}")
        else:
            debug_log(LOGGER, 
                f"Skipping non-matching file: {cache_file['file_name']}")

    debug_log(LOGGER, 
        f"Certificate download completed: {extracted_count} files extracted")
    # List extracted directory contents
    if Path(DATA_PATH).exists():
        contents = list(Path(DATA_PATH).rglob("*"))
        debug_log(LOGGER, f"Extracted directory contains {len(contents)} items")
        for item in contents[:10]:  # Show first 10 items
            debug_log(LOGGER, f"  - {item}")
        if len(contents) > 10:
            debug_log(LOGGER, f"  ... and {len(contents) - 10} more items")


def retrieve_certificates():
    # Retrieve and parse Let's Encrypt certificate information.
    # 
    # Downloads certificates from cache and parses both the certificate
    # files and renewal configuration to extract comprehensive certificate
    # information.
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(LOGGER, "Starting certificate retrieval")
    
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
    
    debug_log(LOGGER, f"Processing {len(cert_files)} certificate files")

    for cert_file in cert_files:
        domain = cert_file.parent.name
        certificates["domain"].append(domain)
        
        debug_log(LOGGER, 
            f"Processing certificate {len(certificates['domain'])}: {domain}")
        debug_log(LOGGER, f"Certificate file path: {cert_file}")
        debug_log(LOGGER, 
            f"Certificate file size: {cert_file.stat().st_size} bytes")
        
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
            debug_log(LOGGER, f"Loading X.509 certificate from {cert_file}")
            
            cert_data = cert_file.read_bytes()
            debug_log(LOGGER, 
                f"Certificate data length: {len(cert_data)} bytes")
            debug_log(LOGGER, 
                f"Certificate starts with: {cert_data[:50]}")
            
            cert = x509.load_pem_x509_certificate(
                cert_data, default_backend()
            )
            
            debug_log(LOGGER, 
                f"Successfully loaded certificate for {domain}")
            debug_log(LOGGER, f"Certificate subject: {cert.subject}")
            debug_log(LOGGER, f"Certificate issuer: {cert.issuer}")
            
            subject = cert.subject.get_attributes_for_oid(
                x509.NameOID.COMMON_NAME
            )
            if subject:
                cert_info["common_name"] = subject[0].value
                debug_log(LOGGER, 
                    f"Certificate CN extracted: {cert_info['common_name']}")
            else:
                debug_log(LOGGER, 
                    "No Common Name found in certificate subject")
            
            issuer = cert.issuer.get_attributes_for_oid(
                x509.NameOID.COMMON_NAME
            )
            if issuer:
                cert_info["issuer"] = issuer[0].value
                debug_log(LOGGER, 
                    f"Certificate issuer extracted: {cert_info['issuer']}")
            else:
                debug_log(LOGGER, 
                    "No Common Name found in certificate issuer")
            
            cert_info["valid_from"] = (
                cert.not_valid_before.astimezone().isoformat()
            )
            cert_info["valid_to"] = (
                cert.not_valid_after.astimezone().isoformat()
            )
            
            debug_log(LOGGER, 
                f"Certificate validity period: {cert_info['valid_from']} to "
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
                    debug_log(LOGGER, f"OCSP URLs found: {ocsp_urls}")
                else:
                    cert_info["ocsp_support"] = "No"
                    debug_log(LOGGER, 
                        "AIA extension found but no OCSP URLs")
                        
            except x509.ExtensionNotFound:
                cert_info["ocsp_support"] = "No"
                debug_log(LOGGER, 
                    "No Authority Information Access extension found")
            except Exception as ocsp_error:
                cert_info["ocsp_support"] = "Unknown"
                debug_log(LOGGER, f"Error checking OCSP support: {ocsp_error}")
            
            debug_log(LOGGER, "Certificate details extracted:")
            debug_log(LOGGER, f"  - Serial: {cert_info['serial_number']}")
            debug_log(LOGGER, 
                f"  - Fingerprint: {cert_info['fingerprint'][:16]}...")
            debug_log(LOGGER, f"  - Version: {cert_info['version']}")
            debug_log(LOGGER, 
                f"  - OCSP Support: {cert_info['ocsp_support']}")
            
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while parsing certificate {cert_file}: {e}")
            debug_log(LOGGER, 
                f"Certificate parsing failed for {domain}: {str(e)}")
            debug_log(LOGGER, f"Error type: {type(e).__name__}")

        try:
            renewal_file = Path(DATA_PATH).joinpath("renewal", 
                                                   f"{domain}.conf")
            if renewal_file.exists():
                debug_log(LOGGER, f"Processing renewal file: {renewal_file}")
                debug_log(LOGGER, 
                    f"Renewal file size: {renewal_file.stat().st_size} bytes")
                
                config_lines_processed = 0
                with renewal_file.open("r") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                            
                        config_lines_processed += 1
                        if is_debug and line_num <= 10:  # Debug first 10 lines
                            debug_log(LOGGER, 
                                f"Renewal config line {line_num}: {line}")
                        
                        if line.startswith("preferred_profile = "):
                            cert_info["preferred_profile"] = (
                                line.split(" = ")[1].strip()
                            )
                            debug_log(LOGGER, 
                                f"Found preferred_profile: "
                                f"{cert_info['preferred_profile']}")
                        elif line.startswith("pref_challs = "):
                            challenges = line.split(" = ")[1].strip()
                            cert_info["challenge"] = challenges.split(",")[0]
                            debug_log(LOGGER, 
                                f"Found challenge: {cert_info['challenge']} "
                                f"(from {challenges})")
                        elif line.startswith("authenticator = "):
                            cert_info["authenticator"] = (
                                line.split(" = ")[1].strip()
                            )
                            debug_log(LOGGER, 
                                f"Found authenticator: "
                                f"{cert_info['authenticator']}")
                        elif line.startswith("server = "):
                            cert_info["issuer_server"] = (
                                line.split(" = ")[1].strip()
                            )
                            debug_log(LOGGER, 
                                f"Found issuer_server: "
                                f"{cert_info['issuer_server']}")
                        elif line.startswith("key_type = "):
                            cert_info["key_type"] = (
                                line.split(" = ")[1].strip()
                            )
                            debug_log(LOGGER, 
                                f"Found key_type: {cert_info['key_type']}")
                
                debug_log(LOGGER, 
                    f"Processed {config_lines_processed} configuration lines")
                debug_log(LOGGER, 
                    f"Final renewal configuration for {domain}:")
                debug_log(LOGGER, 
                    f"  - Profile: {cert_info['preferred_profile']}")
                debug_log(LOGGER, f"  - Challenge: {cert_info['challenge']}")
                debug_log(LOGGER, 
                    f"  - Authenticator: {cert_info['authenticator']}")
                debug_log(LOGGER, 
                    f"  - Server: {cert_info['issuer_server']}")
                debug_log(LOGGER, f"  - Key type: {cert_info['key_type']}")
            else:
                debug_log(LOGGER, 
                    f"No renewal file found for {domain} at {renewal_file}")
                    
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while parsing renewal configuration "
                        f"{renewal_file}: {e}")
            debug_log(LOGGER, 
                f"Renewal config parsing failed for {domain}: {str(e)}")
            debug_log(LOGGER, f"Error type: {type(e).__name__}")

        for key in cert_info:
            certificates[key].append(cert_info[key])

    debug_log(LOGGER, f"Retrieved {len(certificates['domain'])} certificates")
    # Summary of OCSP support
    ocsp_support_counts = {"Yes": 0, "No": 0, "Unknown": 0}
    for ocsp_status in certificates.get('ocsp_support', []):
        ocsp_support_counts[ocsp_status] = (
            ocsp_support_counts.get(ocsp_status, 0) + 1
        )
    debug_log(LOGGER, f"OCSP support summary: {ocsp_support_counts}")

    return certificates


@letsencrypt.route("/letsencrypt", methods=["GET"])
@login_required
def letsencrypt_page():
    # Render the Let's Encrypt certificates management page.
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(LOGGER, "Rendering Let's Encrypt page")
    
    return render_template("letsencrypt.html")


@letsencrypt.route("/letsencrypt/fetch", methods=["POST"])
@login_required
@cors_required
def letsencrypt_fetch():
    # Fetch certificate data for DataTables AJAX requests.
    # 
    # Retrieves and formats certificate information for display in the
    # DataTables interface.
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(LOGGER, "Fetching certificates for DataTables")
    
    cert_list = []

    try:
        certs = retrieve_certificates()
        
        debug_log(LOGGER, f"Retrieved certificates: "
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
            
            debug_log(LOGGER, f"Added certificate to list: {domain}")
            debug_log(LOGGER, 
                f"  - OCSP Support: {cert_data['ocsp_support']}")
            debug_log(LOGGER, f"  - Challenge: {cert_data['challenge']}")
            debug_log(LOGGER, f"  - Key Type: {cert_data['key_type']}")
                
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while fetching certificates: {e}")

    response_data = {
        "data": cert_list,
        "recordsTotal": len(cert_list),
        "recordsFiltered": len(cert_list),
        "draw": int(request.form.get("draw", 1)),
    }
    
    debug_log(LOGGER, f"Returning {len(cert_list)} certificates to DataTables")

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
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    cert_name = request.json.get("cert_name")
    if not cert_name:
        debug_log(LOGGER, "Certificate deletion request missing cert_name")
        return jsonify({"status": "ko", "message": "Missing cert_name"}), 400

    debug_log(LOGGER, f"Starting deletion of certificate: {cert_name}")

    download_certificates()

    env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
    env["PYTHONPATH"] = env["PYTHONPATH"] + (
        f":{DEPS_PATH}" if DEPS_PATH not in env["PYTHONPATH"] else ""
    )

    debug_log(LOGGER, f"Running certbot delete for {cert_name}")
    debug_log(LOGGER, f"Environment: PATH={env['PATH'][:100]}...")
    debug_log(LOGGER, f"PYTHONPATH: {env['PYTHONPATH'][:100]}...")

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

    debug_log(LOGGER, f"Certbot delete return code: {delete_proc.returncode}")
    if delete_proc.stdout:
        debug_log(LOGGER, f"Certbot output: {delete_proc.stdout}")

    if delete_proc.returncode == 0:
        LOGGER.info(f"Successfully deleted certificate {cert_name}")
        
        # Clean up certificate directories and files
        cert_dir = Path(DATA_PATH).joinpath("live", cert_name)
        archive_dir = Path(DATA_PATH).joinpath("archive", cert_name)
        renewal_file = Path(DATA_PATH).joinpath("renewal", 
                                               f"{cert_name}.conf")

        debug_log(LOGGER, f"Cleaning up directories for {cert_name}")

        for path in (cert_dir, archive_dir):
            if path.exists():
                try:
                    for file in path.glob("*"):
                        try:
                            file.unlink()
                            debug_log(LOGGER, f"Removed file: {file}")
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
                debug_log(LOGGER, f"Renewal file removed: {renewal_file}")
            except Exception as e:
                LOGGER.error(f"Failed to remove renewal file "
                           f"{renewal_file}: {e}")

        # Update database cache with modified certificate data
        try:
            debug_log(LOGGER, "Updating database cache with modified data")
            
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
                    
            debug_log(LOGGER, "Database cache updated successfully")
                
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
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(LOGGER, f"Serving static file: {filename}")
    
    return letsencrypt.send_static_file(filename)