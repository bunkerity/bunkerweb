#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from bw_logger import setup_logger
from API import API  # type: ignore

# Initialize bw_logger module for Let's Encrypt certificate deployment
logger = setup_logger(
    title="letsencrypt-certbot-deploy",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-certbot-deploy")
status = 0

try:
    # Get environment variables from Certbot
    token = getenv("CERTBOT_TOKEN", "")
    renewed_domains = getenv('RENEWED_DOMAINS', '')
    logger.debug(f"Environment variables retrieved - token: '{token[:10] if token else ''}...', renewed_domains: '{renewed_domains}'")

    logger.info(f"Certificates renewal for {renewed_domains} successful")

    # Create tarball of /var/cache/bunkerweb/letsencrypt for distribution
    logger.debug("Creating tarball of Let's Encrypt certificates")
    tgz = BytesIO()
    
    # Build certificate archive path
    cert_source_path = join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc")
    logger.debug(f"Certificate source path: {cert_source_path}")

    with tar_open(mode="w:gz", fileobj=tgz, compresslevel=3) as tf:
        logger.debug("Adding certificate directory to tarball")
        tf.add(cert_source_path, arcname="etc")
    
    tgz.seek(0, 0)
    tarball_size = len(tgz.getvalue())
    logger.debug(f"Tarball created successfully with size: {tarball_size} bytes")
    
    files = {"archive.tar.gz": tgz}

    # Connect to database to get instance and service information
    database_uri = getenv("DATABASE_URI")
    logger.debug(f"Connecting to database with URI: {database_uri}")
    db = Database(logger, sqlalchemy_string=database_uri)
    logger.debug("Database connection established successfully")

    # Retrieve all active instances from database
    instances = db.get_instances()
    logger.debug(f"Retrieved {len(instances)} instances from database")
    
    # Get server names for reload timeout calculation
    logger.debug("Retrieving server names for timeout calculation")
    settings_data = db.get_non_default_settings(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))
    services = settings_data["SERVER_NAME"].split(" ")
    logger.debug(f"Found {len(services)} services: {services}")

    # Configure reload timeout with validation
    reload_min_timeout = getenv("RELOAD_MIN_TIMEOUT", "5")
    logger.debug(f"Raw reload timeout from env: '{reload_min_timeout}'")

    if not reload_min_timeout.isdigit():
        logger.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
        reload_min_timeout = 5
    else:
        reload_min_timeout = int(reload_min_timeout)
    
    # Calculate dynamic timeout based on service count
    calculated_timeout = max(reload_min_timeout, 3 * len(services))
    logger.debug(f"Reload timeout configured: min={reload_min_timeout}, calculated={calculated_timeout}")

    # Deploy certificates to each instance
    for i, instance in enumerate(instances):
        hostname = instance['hostname']
        port = instance['port']
        server_name = instance["server_name"]
        
        logger.debug(f"Processing certificate deployment for instance {i+1}/{len(instances)}: "
                   f"{hostname}:{port} (server: {server_name})")
        
        # Create API client for this instance
        endpoint = f"http://{hostname}:{port}"
        api = API(endpoint, host=server_name)
        logger.debug(f"Created API client for {api.endpoint}")

        # Upload certificate archive to instance
        logger.debug(f"Uploading certificate archive to {api.endpoint}/lets-encrypt/certificates")
        sent, err, status_code, resp = api.request("POST", "/lets-encrypt/certificates", files=files)
        logger.debug(f"Certificate upload result - sent: {sent}, status: {status_code}, error: {err}")
        
        # Handle certificate upload response
        if not sent:
            status = 1
            logger.error(f"Can't send API request to {api.endpoint}/lets-encrypt/certificates : {err}")
        elif status_code != 200:
            status = 1
            logger.error(f"Error while sending API request to {api.endpoint}/lets-encrypt/certificates : status = {resp['status']}, msg = {resp['msg']}")
        else:
            logger.info(f"Successfully sent API request to {api.endpoint}/lets-encrypt/certificates")
            logger.debug(f"Certificate archive uploaded successfully to {hostname}:{port}")
            
            # Trigger configuration reload after successful certificate deployment
            disable_testing = getenv('DISABLE_CONFIGURATION_TESTING', 'no').lower() == 'yes'
            test_param = 'no' if disable_testing else 'yes'
            reload_url = f"/reload?test={test_param}"
            
            logger.debug(f"Triggering configuration reload on {api.endpoint}{reload_url} with timeout {calculated_timeout}s")
            sent, err, reload_status, resp = api.request(
                "POST",
                reload_url,
                timeout=calculated_timeout,
            )
            logger.debug(f"Configuration reload result - sent: {sent}, status: {reload_status}, error: {err}")
            
            # Handle reload response
            if not sent:
                status = 1
                logger.error(f"Can't send API request to {api.endpoint}/reload : {err}")
            elif reload_status != 200:
                status = 1
                logger.error(f"Error while sending API request to {api.endpoint}/reload : status = {resp['status']}, msg = {resp['msg']}")
            else:
                logger.info(f"Successfully sent API request to {api.endpoint}/reload")
                logger.debug(f"Configuration reloaded successfully on {hostname}:{port}")

except BaseException as e:
    status = 1
    logger.exception("Exception occurred while deploying Let's Encrypt certificates")
    logger.error(f"Exception details: {type(e).__name__}: {e}")

logger.debug(f"Certificate deployment completed with exit status: {status}")
sys_exit(status)
