#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from API import API  # type: ignore

LOGGER = setup_logger("Lets-encrypt.deploy")
status = 0

try:
    # Get environment variables for certificate deployment
    # CERTBOT_TOKEN: Token from certbot (currently unused but preserved)
    # RENEWED_DOMAINS: Domains that were successfully renewed
    token = getenv("CERTBOT_TOKEN", "")
    renewed_domains = getenv("RENEWED_DOMAINS", "")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Certificate deployment started")
        LOGGER.debug(f"Token: {token[:10] if token else 'None'}...")
        LOGGER.debug(f"Renewed domains: {renewed_domains}")

    LOGGER.info(f"Certificates renewal for {renewed_domains} successful")

    # Create tarball of certificate directory for distribution
    # This packages all certificate files into a compressed archive
    # for efficient transfer to cluster instances
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Creating certificate archive for distribution")
    
    tgz = BytesIO()
    cert_source_path = join(sep, "var", "cache", "bunkerweb", "letsencrypt", "etc")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Source certificate path: {cert_source_path}")

    # Create compressed tarball containing certificate files
    # compresslevel=3 provides good compression with reasonable performance
    with tar_open(mode="w:gz", fileobj=tgz, compresslevel=3) as tf:
        tf.add(cert_source_path, arcname="etc")
    
    # Reset buffer position for reading
    tgz.seek(0, 0)
    files = {"archive.tar.gz": tgz}
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Certificate archive created, size: {tgz.getbuffer().nbytes} bytes")

    # Initialize database connection to get cluster instances
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Initializing database connection")
    
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
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Retrieved {len(instances)} instances from database")
        LOGGER.debug(f"Found {len(services)} configured services: {services}")
        for i, instance in enumerate(instances):
            LOGGER.debug(
                f"Instance {i+1}: {instance['hostname']}:"
                f"{instance['port']} (server: {instance.get('server_name', 'N/A')})"
            )

    # Configure reload timeout based on environment and service count
    # Minimum timeout prevents premature timeouts on slow systems
    reload_min_timeout = getenv("RELOAD_MIN_TIMEOUT", "5")

    if not reload_min_timeout.isdigit():
        LOGGER.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
        reload_min_timeout = 5

    reload_min_timeout = int(reload_min_timeout)
    
    # Calculate actual timeout: minimum timeout or 3 seconds per service
    calculated_timeout = max(reload_min_timeout, 3 * len(services))
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Reload timeout configuration:")
        LOGGER.debug(f"  Minimum timeout: {reload_min_timeout}s")
        LOGGER.debug(f"  Service count: {len(services)}")
        LOGGER.debug(f"  Calculated timeout: {calculated_timeout}s")

    LOGGER.info(f"Deploying certificates to {len(instances)} instances")

    # Deploy certificates to each cluster instance
    for i, instance in enumerate(instances):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Processing instance {i+1}/{len(instances)}")
        
        # Construct API endpoint for this instance
        endpoint = f"http://{instance['hostname']}:{instance['port']}"
        host = instance["server_name"]
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Connecting to: {endpoint} (host: {host})")
        
        api = API(endpoint, host=host)

        # Upload certificate archive to the instance
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Uploading certificate archive to {endpoint}")
        
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
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Certificate upload failed with error: {err}")
            continue
        elif status_code != 200:
            status = 1
            LOGGER.error(
                f"Error while sending API request to "
                f"{api.endpoint}/lets-encrypt/certificates: "
                f"status = {resp['status']}, msg = {resp['msg']}"
            )
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Certificate upload response: {resp}")
            continue
        else:
            LOGGER.info(
                f"Successfully sent API request to "
                f"{api.endpoint}/lets-encrypt/certificates"
            )
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Certificate archive uploaded successfully")
            
            # Trigger configuration reload on the instance
            # Configuration testing can be disabled via environment variable
            disable_testing = getenv("DISABLE_CONFIGURATION_TESTING", "no").lower()
            test_config = "no" if disable_testing == "yes" else "yes"
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Triggering reload on {endpoint}")
                LOGGER.debug(f"Configuration testing: {test_config}")
                LOGGER.debug(f"Reload timeout: {calculated_timeout}s")
            
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
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Reload request failed with error: {err}")
            elif status_code != 200:
                status = 1
                LOGGER.error(
                    f"Error while sending API request to {api.endpoint}/reload: "
                    f"status = {resp['status']}, msg = {resp['msg']}"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Reload response: {resp}")
            else:
                LOGGER.info(f"Successfully sent API request to {api.endpoint}/reload")
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Instance {endpoint} reloaded successfully")

        # Reset file pointer for next instance
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Resetting archive buffer for next instance")
        tgz.seek(0, 0)

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Certificate deployment process completed")

except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-deploy.py:\n{e}")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Full exception traceback logged above")

if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    LOGGER.debug(f"Certificate deployment completed with status: {status}")

sys_exit(status)