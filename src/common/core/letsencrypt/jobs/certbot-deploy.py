#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from API import API  # type: ignore

LOGGER = setup_logger("Lets-encrypt.deploy")
status = 0


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


try:
    # Get environment variables for certificate deployment
    # CERTBOT_TOKEN: Token from certbot (currently unused but preserved)
    # RENEWED_DOMAINS: Domains that were successfully renewed
    token = getenv("CERTBOT_TOKEN", "")
    renewed_domains = getenv("RENEWED_DOMAINS", "")
    
    debug_log(LOGGER, "Certificate deployment started")
    debug_log(LOGGER, f"Token: {token[:10] if token else 'None'}...")
    debug_log(LOGGER, f"Renewed domains: {renewed_domains}")
    debug_log(LOGGER, 
        "Starting certificate distribution to cluster instances")
    debug_log(LOGGER, 
        "This process will update certificates on all instances")

    LOGGER.info(f"Certificates renewal for {renewed_domains} successful")

    # Create tarball of certificate directory for distribution
    # This packages all certificate files into a compressed archive
    # for efficient transfer to cluster instances
    debug_log(LOGGER, "Creating certificate archive for distribution")
    debug_log(LOGGER, 
        "Packaging all Let's Encrypt certificates into tarball")
    debug_log(LOGGER, 
        "Archive will contain fullchain.pem and privkey.pem files")
    
    tgz = BytesIO()
    cert_source_path = join(sep, "var", "cache", "bunkerweb", "letsencrypt", 
                           "etc")
    
    debug_log(LOGGER, f"Source certificate path: {cert_source_path}")
    debug_log(LOGGER, "Checking if certificate directory exists")
    cert_path_exists = Path(cert_source_path).exists()
    debug_log(LOGGER, f"Certificate directory exists: {cert_path_exists}")

    # Create compressed tarball containing certificate files
    # compresslevel=3 provides good compression with reasonable performance
    with tar_open(mode="w:gz", fileobj=tgz, compresslevel=3) as tf:
        tf.add(cert_source_path, arcname="etc")
    
    # Reset buffer position for reading
    tgz.seek(0, 0)
    files = {"archive.tar.gz": tgz}
    
    archive_size = tgz.getbuffer().nbytes
    debug_log(LOGGER, "Certificate archive created successfully")
    debug_log(LOGGER, f"Archive size: {archive_size} bytes")
    debug_log(LOGGER, "Compression level: 3 (balanced speed/size)")
    debug_log(LOGGER, "Archive ready for distribution to instances")

    # Initialize database connection to get cluster instances
    debug_log(LOGGER, "Initializing database connection")
    debug_log(LOGGER, 
        "Need to get list of active BunkerWeb instances")
    
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

    # Get all active BunkerWeb instances for certificate distribution
    instances = db.get_instances()
    
    # Get server names to calculate appropriate reload timeout
    # More services require longer timeout for configuration reload
    services = db.get_non_default_settings(
        global_only=True, 
        methods=False, 
        with_drafts=True, 
        filtered_settings=("SERVER_NAME",)
    )["SERVER_NAME"].split(" ")
    
    debug_log(LOGGER, f"Retrieved {len(instances)} instances from database")
    debug_log(LOGGER, 
        f"Found {len(services)} configured services: {services}")
    debug_log(LOGGER, "Instance details for certificate deployment:")
    for i, instance in enumerate(instances):
        debug_log(LOGGER, 
            f"  Instance {i+1}: {instance['hostname']}:"
            f"{instance['port']} (server: "
            f"{instance.get('server_name', 'N/A')})")
    debug_log(LOGGER, 
        "Will deploy certificates and trigger reload on each instance")

    # Configure reload timeout based on environment and service count
    # Minimum timeout prevents premature timeouts on slow systems
    reload_min_timeout = getenv("RELOAD_MIN_TIMEOUT", "5")

    if not reload_min_timeout.isdigit():
        LOGGER.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
        reload_min_timeout = 5

    reload_min_timeout = int(reload_min_timeout)
    
    # Calculate actual timeout: minimum timeout or 3 seconds per service
    calculated_timeout = max(reload_min_timeout, 3 * len(services))
    
    debug_log(LOGGER, "Reload timeout configuration:")
    debug_log(LOGGER, f"  Minimum timeout setting: {reload_min_timeout}s")
    debug_log(LOGGER, f"  Number of services: {len(services)}")
    debug_log(LOGGER, 
        f"  Calculated timeout (max of min or 3s per service): "
        f"{calculated_timeout}s")
    debug_log(LOGGER, 
        "Timeout ensures all services have time to reload certificates")

    LOGGER.info(f"Deploying certificates to {len(instances)} instances")

    # Deploy certificates to each cluster instance
    for i, instance in enumerate(instances):
        debug_log(LOGGER, f"Processing instance {i+1}/{len(instances)}")
        debug_log(LOGGER, 
            f"Current instance: {instance['hostname']}:{instance['port']}")
        
        # Construct API endpoint for this instance
        endpoint = f"http://{instance['hostname']}:{instance['port']}"
        host = instance["server_name"]
        
        debug_log(LOGGER, f"API endpoint: {endpoint}")
        debug_log(LOGGER, f"Host header: {host}")
        debug_log(LOGGER, "Creating API client for certificate upload")
        
        api = API(endpoint, host=host)

        # Upload certificate archive to the instance
        debug_log(LOGGER, f"Uploading certificate archive to {endpoint}")
        debug_log(LOGGER, "Sending POST request with certificate tarball")
        debug_log(LOGGER, 
            "This will extract certificates to instance filesystem")
        
        sent, err, status_code, resp = api.request(
            "POST", 
            "/lets-encrypt/certificates", 
            files=files
        )
        
        if not sent:
            status = 1
            LOGGER.error(
                f"Can't send API request to "
                f"{api.endpoint}/lets-encrypt/certificates: {err}"
            )
            debug_log(LOGGER, f"Certificate upload failed with error: {err}")
            debug_log(LOGGER, 
                "Skipping reload for this instance due to upload failure")
            continue
        elif status_code != 200:
            status = 1
            LOGGER.error(
                f"Error while sending API request to "
                f"{api.endpoint}/lets-encrypt/certificates: "
                f"status = {resp['status']}, msg = {resp['msg']}"
            )
            debug_log(LOGGER, f"HTTP status code: {status_code}")
            debug_log(LOGGER, f"Error response: {resp}")
            debug_log(LOGGER, "Certificate upload failed, skipping reload")
            continue
        else:
            LOGGER.info(
                f"Successfully sent API request to "
                f"{api.endpoint}/lets-encrypt/certificates"
            )
            debug_log(LOGGER, "Certificate archive uploaded successfully")
            debug_log(LOGGER, 
                "Certificates are now available on instance filesystem")
            debug_log(LOGGER, "Proceeding to trigger configuration reload")
            
            # Trigger configuration reload on the instance
            # Configuration testing can be disabled via environment variable
            disable_testing = getenv("DISABLE_CONFIGURATION_TESTING", 
                                   "no").lower()
            test_config = "no" if disable_testing == "yes" else "yes"
            
            debug_log(LOGGER, f"Triggering configuration reload on {endpoint}")
            debug_log(LOGGER, f"Configuration testing enabled: {test_config}")
            debug_log(LOGGER, f"Reload timeout: {calculated_timeout}s")
            debug_log(LOGGER, "This will reload nginx with new certificates")
            
            sent, err, status_code, resp = api.request(
                "POST",
                f"/reload?test={test_config}",
                timeout=calculated_timeout,
            )
            
            if not sent:
                status = 1
                LOGGER.error(
                    f"Can't send API request to {api.endpoint}/reload: {err}"
                )
                debug_log(LOGGER, f"Reload request failed with error: {err}")
                debug_log(LOGGER, 
                    "Instance may not have reloaded new certificates")
            elif status_code != 200:
                status = 1
                LOGGER.error(
                    f"Error while sending API request to {api.endpoint}/reload: "
                    f"status = {resp['status']}, msg = {resp['msg']}"
                )
                debug_log(LOGGER, f"HTTP status code: {status_code}")
                debug_log(LOGGER, f"Reload response: {resp}")
                debug_log(LOGGER, 
                    "Configuration reload failed on this instance")
            else:
                LOGGER.info(
                    f"Successfully sent API request to {api.endpoint}/reload")
                debug_log(LOGGER, "Configuration reload completed successfully")
                debug_log(LOGGER, 
                    "New certificates are now active on this instance")
                debug_log(LOGGER, f"Instance {endpoint} fully updated")

        # Reset file pointer for next instance
        debug_log(LOGGER, 
            "Resetting archive buffer position for next instance")
        debug_log(LOGGER, 
            "Archive will be re-read from beginning for next upload")
        tgz.seek(0, 0)

    debug_log(LOGGER, "Certificate deployment process completed")
    debug_log(LOGGER, "All instances have been processed")
    if status == 0:
        debug_log(LOGGER, "All deployments successful")
    else:
        debug_log(LOGGER, 
            "Some deployments failed - check individual instance logs")

except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-deploy.py:\n{e}")
    
    debug_log(LOGGER, "Full exception traceback logged above")
    debug_log(LOGGER, "Certificate deployment failed due to exception")
    debug_log(LOGGER, 
        "Some instances may not have received updated certificates")

debug_log(LOGGER, 
    f"Certificate deployment completed with final status: {status}")
if status == 0:
    debug_log(LOGGER, 
        "All certificates deployed successfully across cluster")
else:
    debug_log(LOGGER, 
        "Deployment completed with errors - manual intervention may be needed")

sys_exit(status)