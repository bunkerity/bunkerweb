#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from common_utils import get_integration  # type: ignore
from logger import setup_logger  # type: ignore
from API import API  # type: ignore

LOGGER = setup_logger("Lets-encrypt.auth")
status = 0

try:
    # Get environment variables for ACME HTTP challenge
    # CERTBOT_TOKEN: The filename for the challenge file
    # CERTBOT_VALIDATION: The content to write to the challenge file
    token = getenv("CERTBOT_TOKEN", "")
    validation = getenv("CERTBOT_VALIDATION", "")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("ACME HTTP challenge authentication started")
        LOGGER.debug(f"Token: {token[:10] if token else 'None'}...")
        LOGGER.debug(f"Validation length: {len(validation) if validation else 0} chars")
        LOGGER.debug("Checking for required environment variables")
        LOGGER.debug(f"CERTBOT_TOKEN exists: {bool(token)}")
        LOGGER.debug(f"CERTBOT_VALIDATION exists: {bool(validation)}")
    
    # Detect the current BunkerWeb integration type
    # This determines how we handle the challenge deployment
    integration = get_integration()
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Integration detection completed: {integration}")
        LOGGER.debug("Determining challenge deployment method based on integration")

    LOGGER.info(f"Detected {integration} integration")

    # Cluster case: Docker, Swarm, Kubernetes, Autoconf
    # For cluster deployments, we need to distribute the challenge
    # to all instances via the BunkerWeb API
    if integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Cluster integration detected, initializing database connection")
            LOGGER.debug("Will distribute challenge to all cluster instances via API")
        
        # Initialize database connection to get list of instances
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

        # Get all active BunkerWeb instances from the database
        instances = db.get_instances()
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Retrieved {len(instances)} instances from database")
            LOGGER.debug("Instance details:")
            for i, instance in enumerate(instances):
                LOGGER.debug(
                    f"  Instance {i+1}: {instance['hostname']}:"
                    f"{instance['port']} (server: {instance.get('server_name', 'N/A')})"
                )
            LOGGER.debug("Preparing to send challenge data to each instance")

        LOGGER.info(f"Sending challenge to {len(instances)} instances")
        
        # Send challenge to each instance via API
        for instance in instances:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(
                    f"Processing instance: {instance['hostname']}:{instance['port']}"
                )
                LOGGER.debug(f"Server name: {instance.get('server_name', 'N/A')}")
                LOGGER.debug("Creating API client for this instance")
            
            # Create API client for this instance
            api = API(
                f"http://{instance['hostname']}:{instance['port']}", 
                host=instance["server_name"]
            )
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"API endpoint: {api.endpoint}")
                LOGGER.debug("Preparing challenge data payload")
                LOGGER.debug(f"Token: {token[:10]}... (truncated)")
                LOGGER.debug(f"Validation length: {len(validation)} characters")
            
            # Send POST request to deploy the challenge
            sent, err, status_code, resp = api.request(
                "POST", 
                "/lets-encrypt/challenge", 
                data={"token": token, "validation": validation}
            )
            
            if not sent:
                status = 1
                LOGGER.error(
                    f"Can't send API request to "
                    f"{api.endpoint}/lets-encrypt/challenge: {err}"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"API request failed with error: {err}")
                    LOGGER.debug("This instance will not receive the challenge")
            elif status_code != 200:
                status = 1
                LOGGER.error(
                    f"Error while sending API request to "
                    f"{api.endpoint}/lets-encrypt/challenge: "
                    f"status = {resp['status']}, msg = {resp['msg']}"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"HTTP status code: {status_code}")
                    LOGGER.debug(f"Response details: {resp}")
                    LOGGER.debug("Challenge deployment failed for this instance")
            else:
                LOGGER.info(
                    f"Successfully sent API request to "
                    f"{api.endpoint}/lets-encrypt/challenge"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"HTTP status code: {status_code}")
                    LOGGER.debug("Challenge successfully deployed to instance")
                    LOGGER.debug(f"Instance can now serve challenge at /.well-known/acme-challenge/{token}")

    # Linux case: Standalone installation
    # For standalone Linux installations, we write the challenge
    # file directly to the local filesystem
    else:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Standalone Linux integration detected")
            LOGGER.debug("Writing challenge file directly to local filesystem")
            LOGGER.debug("No API distribution needed for standalone mode")
        
        # Create the ACME challenge directory structure
        # This follows the standard .well-known/acme-challenge path
        root_dir = Path(
            sep, "var", "tmp", "bunkerweb", "lets-encrypt", 
            ".well-known", "acme-challenge"
        )
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Challenge directory path: {root_dir}")
            LOGGER.debug("Creating directory structure if it doesn't exist")
            LOGGER.debug("Directory will be created with parents=True, exist_ok=True")
        
        # Create directory structure with appropriate permissions
        root_dir.mkdir(parents=True, exist_ok=True)
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Directory structure created successfully")
            LOGGER.debug(f"Directory exists: {root_dir.exists()}")
            LOGGER.debug(f"Directory is writable: {root_dir.is_dir()}")
        
        # Write the challenge validation content to the token file
        challenge_file = root_dir.joinpath(token)
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Challenge file path: {challenge_file}")
            LOGGER.debug(f"Token filename: {token}")
            LOGGER.debug(f"Validation content length: {len(validation)} bytes")
            LOGGER.debug("Writing validation content to challenge file")
        
        challenge_file.write_text(validation, encoding="utf-8")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Challenge file written successfully")
            LOGGER.debug(f"File exists: {challenge_file.exists()}")
            LOGGER.debug(f"File size: {challenge_file.stat().st_size} bytes")
            LOGGER.debug("Let's Encrypt can now access the challenge file")
        
        LOGGER.info(f"Challenge file created at {challenge_file}")

except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-auth.py:\n{e}")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Full exception traceback logged above")
        LOGGER.debug("Authentication process failed due to exception")
        LOGGER.debug("Let's Encrypt challenge will not be available")

if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    LOGGER.debug(f"ACME HTTP challenge authentication completed with status: {status}")
    if status == 0:
        LOGGER.debug("Authentication completed successfully")
        LOGGER.debug("Let's Encrypt can now access the challenge")
    else:
        LOGGER.debug("Authentication failed - challenge may not be accessible")

sys_exit(status)