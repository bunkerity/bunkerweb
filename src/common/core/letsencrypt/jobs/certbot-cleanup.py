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

LOGGER = setup_logger("Lets-encrypt.cleanup")
status = 0

try:
    # Get environment variables for ACME HTTP challenge cleanup
    # CERTBOT_TOKEN: The filename of the challenge file to remove
    token = getenv("CERTBOT_TOKEN", "")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("ACME HTTP challenge cleanup started")
        LOGGER.debug(f"Token to clean: {token[:10] if token else 'None'}...")
        LOGGER.debug("Starting cleanup process for Let's Encrypt challenge")
        LOGGER.debug("This will remove challenge files from all instances")
    
    # Detect the current BunkerWeb integration type
    # This determines how we handle the challenge cleanup process
    integration = get_integration()
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Integration detection completed: {integration}")
        LOGGER.debug("Determining cleanup method based on integration type")

    LOGGER.info(f"Detected {integration} integration")

    # Cluster case: Docker, Swarm, Kubernetes, Autoconf
    # For cluster deployments, we need to remove the challenge
    # from all instances via the BunkerWeb API
    if integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Cluster integration detected")
            LOGGER.debug("Will remove challenge from all cluster instances via API")
            LOGGER.debug("Initializing database connection to get instance list")
        
        # Initialize database connection to get list of instances
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
        
        # Get all active BunkerWeb instances from the database
        instances = db.get_instances()
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Retrieved {len(instances)} instances from database")
            LOGGER.debug("Instance details for cleanup:")
            for i, instance in enumerate(instances):
                LOGGER.debug(
                    f"  Instance {i+1}: {instance['hostname']}:"
                    f"{instance['port']} (server: {instance.get('server_name', 'N/A')})"
                )
            LOGGER.debug("Preparing to send DELETE requests to each instance")

        LOGGER.info(f"Cleaning challenge from {len(instances)} instances")
        
        # Remove challenge from each instance via API
        for instance in instances:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(
                    f"Processing cleanup for instance: "
                    f"{instance['hostname']}:{instance['port']}"
                )
                LOGGER.debug(f"Server name: {instance.get('server_name', 'N/A')}")
                LOGGER.debug("Creating API client for cleanup request")
            
            # Create API client for this instance
            api = API(
                f"http://{instance['hostname']}:{instance['port']}", 
                host=instance["server_name"]
            )
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"API endpoint: {api.endpoint}")
                LOGGER.debug("Preparing DELETE request for challenge cleanup")
                LOGGER.debug(f"Token to delete: {token}")
            
            # Send DELETE request to remove the challenge
            sent, err, status_code, resp = api.request(
                "DELETE", 
                "/lets-encrypt/challenge", 
                data={"token": token}
            )
            
            if not sent:
                status = 1
                LOGGER.error(
                    f"Can't send API request to "
                    f"{api.endpoint}/lets-encrypt/challenge: {err}"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"DELETE request failed with error: {err}")
                    LOGGER.debug("Challenge file may remain on this instance")
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
                    LOGGER.debug("Challenge cleanup failed for this instance")
            else:
                LOGGER.info(
                    f"Successfully sent API request to "
                    f"{api.endpoint}/lets-encrypt/challenge"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"HTTP status code: {status_code}")
                    LOGGER.debug("Challenge successfully removed from instance")
                    LOGGER.debug(f"Token {token} has been cleaned up")

    # Linux case: Standalone installation
    # For standalone Linux installations, we remove the challenge
    # file directly from the local filesystem
    else:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Standalone Linux integration detected")
            LOGGER.debug("Removing challenge file directly from local filesystem")
            LOGGER.debug("No API cleanup needed for standalone mode")
        
        # Construct path to the ACME challenge file
        # This follows the standard .well-known/acme-challenge path
        challenge_file = Path(
            sep, "var", "tmp", "bunkerweb", "lets-encrypt", 
            ".well-known", "acme-challenge", token
        )
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Challenge file path: {challenge_file}")
            LOGGER.debug(f"Token filename: {token}")
            LOGGER.debug("Checking if challenge file exists before cleanup")
            LOGGER.debug(f"File exists before cleanup: {challenge_file.exists()}")
            if challenge_file.exists():
                LOGGER.debug(f"File size: {challenge_file.stat().st_size} bytes")
        
        # Remove the challenge file if it exists
        # missing_ok=True prevents errors if file doesn't exist
        challenge_file.unlink(missing_ok=True)
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Challenge file unlink operation completed")
            LOGGER.debug(f"File exists after cleanup: {challenge_file.exists()}")
            LOGGER.debug("Local challenge file cleanup completed successfully")
            LOGGER.debug("Challenge is no longer accessible to Let's Encrypt")
        
        LOGGER.info(f"Challenge file removed: {challenge_file}")

except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-cleanup.py:\n{e}")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Full exception traceback logged above")
        LOGGER.debug("Cleanup process failed due to exception")
        LOGGER.debug("Some challenge files may remain uncleaned")

if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    LOGGER.debug(f"ACME HTTP challenge cleanup completed with status: {status}")
    if status == 0:
        LOGGER.debug("Cleanup completed successfully")
        LOGGER.debug("All challenge files have been removed")
    else:
        LOGGER.debug("Cleanup encountered errors - some files may remain")

sys_exit(status)