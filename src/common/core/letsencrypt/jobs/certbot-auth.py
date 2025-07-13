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

# Initialize bw_logger module for Let's Encrypt authentication
logger = setup_logger(
    title="letsencrypt-certbot-auth",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-certbot-auth")
status = 0

try:
    # Get environment variables from Certbot
    token = getenv("CERTBOT_TOKEN", "")
    validation = getenv("CERTBOT_VALIDATION", "")
    logger.debug(f"Environment variables retrieved - token: '{token[:10] if token else ''}...', "
                f"validation length: {len(validation)} chars")
    
    # Detect the current integration type (Docker, Kubernetes, etc.)
    integration = get_integration()
    logger.debug(f"Integration detection completed: {integration}")

    logger.info(f"Detected {integration} integration")

    # Handle cluster-based integrations (distribute to all instances)
    if integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        logger.debug("Processing cluster integration mode - distributing challenge")
        
        # Connect to database to get instance list
        database_uri = getenv("DATABASE_URI")
        logger.debug(f"Connecting to database with URI: {database_uri}")
        db = Database(logger, sqlalchemy_string=database_uri)
        logger.debug("Database connection established successfully")

        # Retrieve all active instances from database
        instances = db.get_instances()
        logger.debug(f"Retrieved {len(instances)} instances from database")

        logger.info(f"Sending challenge to {len(instances)} instances")
        
        # Send challenge to each instance via API
        for i, instance in enumerate(instances):
            hostname = instance['hostname']
            port = instance['port']
            server_name = instance["server_name"]
            
            logger.debug(f"Processing instance {i+1}/{len(instances)}: "
                       f"{hostname}:{port} (server: {server_name})")
            
            # Create API client for this instance
            api_endpoint = f"http://{hostname}:{port}"
            api = API(api_endpoint, host=server_name)
            logger.debug(f"Created API client for {api.endpoint}")
            
            # Send POST request with challenge data
            challenge_data = {"token": token, "validation": validation}
            logger.debug(f"Sending challenge data to {api.endpoint}/lets-encrypt/challenge")
            
            sent, err, status_code, resp = api.request("POST", "/lets-encrypt/challenge", data=challenge_data)
            logger.debug(f"API request completed - sent: {sent}, status: {status_code}, error: {err}")
            
            # Handle API response
            if not sent:
                status = 1
                logger.error(f"Can't send API request to {api.endpoint}/lets-encrypt/challenge : {err}")
            elif status_code != 200:
                status = 1
                logger.error(f"Error while sending API request to {api.endpoint}/lets-encrypt/challenge : status = {resp['status']}, msg = {resp['msg']}")
            else:
                logger.info(f"Successfully sent API request to {api.endpoint}/lets-encrypt/challenge")
                logger.debug(f"Challenge distributed to instance {hostname}:{port}")

    # Handle standalone Linux integration (write to local filesystem)
    else:
        logger.debug("Processing standalone Linux integration - writing local file")
        
        # Create directory structure for ACME challenge
        root_dir = Path(sep, "var", "tmp", "bunkerweb", "lets-encrypt", ".well-known", "acme-challenge")
        logger.debug(f"Target challenge directory: {root_dir}")
        
        # Ensure directory exists
        logger.debug("Creating directory structure if it doesn't exist")
        root_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Directory structure verified/created successfully")
        
        # Write challenge token to file
        token_file = root_dir.joinpath(token)
        logger.debug(f"Writing validation to token file: {token_file}")
        token_file.write_text(validation, encoding="utf-8")
        logger.debug(f"Token file written successfully with {len(validation)} chars")
        
except BaseException as e:
    status = 1
    logger.exception("Exception occurred while processing Let's Encrypt challenge")
    logger.error(f"Exception details: {type(e).__name__}: {e}")

logger.debug(f"Script execution completed with exit status: {status}")
sys_exit(status)
