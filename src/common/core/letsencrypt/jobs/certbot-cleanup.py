#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from common_utils import get_integration  # type: ignore
from bw_logger import setup_logger
from API import API  # type: ignore

# Initialize bw_logger module for Let's Encrypt cleanup
logger = setup_logger(
    title="letsencrypt-certbot-cleanup",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-certbot-cleanup")
status = 0

try:
    # Get environment variables from Certbot
    token = getenv("CERTBOT_TOKEN", "")
    logger.debug(f"Environment variables retrieved - token: '{token[:10] if token else ''}...'")
    
    # Detect the current integration type (Docker, Kubernetes, etc.)
    integration = get_integration()
    logger.debug(f"Integration detection completed: {integration}")

    logger.info(f"Detected {integration} integration")

    # Handle cluster-based integrations (clean from all instances)
    if integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        logger.debug("Processing cluster integration mode - cleaning challenge from all instances")
        
        # Connect to database to get instance list
        database_uri = getenv("DATABASE_URI")
        logger.debug(f"Connecting to database with URI: {database_uri}")
        db = Database(logger, sqlalchemy_string=database_uri)
        logger.debug("Database connection established successfully")
        
        # Retrieve all active instances from database
        instances = db.get_instances()
        logger.debug(f"Retrieved {len(instances)} instances from database")

        logger.info(f"Cleaning challenge from {len(instances)} instances")
        
        # Send cleanup request to each instance via API
        for i, instance in enumerate(instances):
            hostname = instance['hostname']
            port = instance['port']
            server_name = instance["server_name"]
            
            logger.debug(f"Processing cleanup for instance {i+1}/{len(instances)}: "
                       f"{hostname}:{port} (server: {server_name})")
            
            # Create API client for this instance
            api_endpoint = f"http://{hostname}:{port}"
            api = API(api_endpoint, host=server_name)
            logger.debug(f"Created API client for {api.endpoint}")
            
            # Send DELETE request to remove challenge
            cleanup_data = {"token": token}
            logger.debug(f"Sending cleanup request to {api.endpoint}/lets-encrypt/challenge")
            
            sent, err, status_code, resp = api.request("DELETE", "/lets-encrypt/challenge", data=cleanup_data)
            logger.debug(f"API cleanup request completed - sent: {sent}, status: {status_code}, error: {err}")
            
            # Handle API response
            if not sent:
                status = 1
                logger.error(f"Can't send API request to {api.endpoint}/lets-encrypt/challenge : {err}")
            elif status_code != 200:
                status = 1
                logger.error(f"Error while sending API request to {api.endpoint}/lets-encrypt/challenge : status = {resp['status']}, msg = {resp['msg']}")
            else:
                logger.info(f"Successfully sent API request to {api.endpoint}/lets-encrypt/challenge")
                logger.debug(f"Challenge cleaned from instance {hostname}:{port}")
                
    # Handle standalone Linux integration (remove local file)
    else:
        logger.debug("Processing standalone Linux integration - removing local challenge file")
        
        # Remove challenge token file from local filesystem
        token_file = Path(sep, "var", "tmp", "bunkerweb", "lets-encrypt", ".well-known", "acme-challenge", token)
        logger.debug(f"Target challenge file to remove: {token_file}")
        
        # Check if file exists before attempting removal
        if token_file.exists():
            logger.debug(f"Challenge file exists, removing: {token_file}")
            token_file.unlink(missing_ok=True)
            logger.debug("Challenge file removed successfully")
            logger.info(f"Cleaned up challenge file: {token_file}")
        else:
            logger.debug(f"Challenge file does not exist, no cleanup needed: {token_file}")
            logger.info("No challenge file found to clean up")
            
except BaseException as e:
    status = 1
    logger.exception("Exception occurred while cleaning Let's Encrypt challenge")
    logger.error(f"Exception details: {type(e).__name__}: {e}")

logger.debug(f"Cleanup script completed with exit status: {status}")
sys_exit(status)
