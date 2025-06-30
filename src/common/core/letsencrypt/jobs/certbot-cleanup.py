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


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


try:
    # Get environment variables for ACME HTTP challenge cleanup
    # CERTBOT_TOKEN: The filename of the challenge file to remove
    token = getenv("CERTBOT_TOKEN", "")
    
    debug_log(LOGGER, "ACME HTTP challenge cleanup started")
    debug_log(LOGGER, f"Token to clean: {token[:10] if token else 'None'}...")
    debug_log(LOGGER, 
        "Starting cleanup process for Let's Encrypt challenge")
    debug_log(LOGGER, 
        "This will remove challenge files from all instances")
    
    # Detect the current BunkerWeb integration type
    # This determines how we handle the challenge cleanup process
    integration = get_integration()
    
    debug_log(LOGGER, f"Integration detection completed: {integration}")
    debug_log(LOGGER, 
        "Determining cleanup method based on integration type")

    LOGGER.info(f"Detected {integration} integration")

    # Cluster case: Docker, Swarm, Kubernetes, Autoconf
    # For cluster deployments, we need to remove the challenge
    # from all instances via the BunkerWeb API
    if integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        debug_log(LOGGER, "Cluster integration detected")
        debug_log(LOGGER, 
            "Will remove challenge from all cluster instances via API")
        debug_log(LOGGER, 
            "Initializing database connection to get instance list")
        
        # Initialize database connection to get list of instances
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
        
        # Get all active BunkerWeb instances from the database
        instances = db.get_instances()
        
        debug_log(LOGGER, f"Retrieved {len(instances)} instances from database")
        debug_log(LOGGER, "Instance details for cleanup:")
        for i, instance in enumerate(instances):
            debug_log(LOGGER, 
                f"  Instance {i+1}: {instance['hostname']}:"
                f"{instance['port']} (server: "
                f"{instance.get('server_name', 'N/A')})")
        debug_log(LOGGER, 
            "Preparing to send DELETE requests to each instance")

        LOGGER.info(f"Cleaning challenge from {len(instances)} instances")
        
        # Remove challenge from each instance via API
        for instance in instances:
            debug_log(LOGGER, 
                f"Processing cleanup for instance: "
                f"{instance['hostname']}:{instance['port']}")
            debug_log(LOGGER, 
                f"Server name: {instance.get('server_name', 'N/A')}")
            debug_log(LOGGER, "Creating API client for cleanup request")
            
            # Create API client for this instance
            api = API(
                f"http://{instance['hostname']}:{instance['port']}", 
                host=instance["server_name"]
            )
            
            debug_log(LOGGER, f"API endpoint: {api.endpoint}")
            debug_log(LOGGER, "Preparing DELETE request for challenge cleanup")
            debug_log(LOGGER, f"Token to delete: {token}")
            
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
                debug_log(LOGGER, f"DELETE request failed with error: {err}")
                debug_log(LOGGER, 
                    "Challenge file may remain on this instance")
            elif status_code != 200:
                status = 1
                LOGGER.error(
                    f"Error while sending API request to "
                    f"{api.endpoint}/lets-encrypt/challenge: "
                    f"status = {resp['status']}, msg = {resp['msg']}"
                )
                debug_log(LOGGER, f"HTTP status code: {status_code}")
                debug_log(LOGGER, f"Response details: {resp}")
                debug_log(LOGGER, 
                    "Challenge cleanup failed for this instance")
            else:
                LOGGER.info(
                    f"Successfully sent API request to "
                    f"{api.endpoint}/lets-encrypt/challenge"
                )
                debug_log(LOGGER, f"HTTP status code: {status_code}")
                debug_log(LOGGER, 
                    "Challenge successfully removed from instance")
                debug_log(LOGGER, f"Token {token} has been cleaned up")

    # Linux case: Standalone installation
    # For standalone Linux installations, we remove the challenge
    # file directly from the local filesystem
    else:
        debug_log(LOGGER, "Standalone Linux integration detected")
        debug_log(LOGGER, 
            "Removing challenge file directly from local filesystem")
        debug_log(LOGGER, "No API cleanup needed for standalone mode")
        
        # Construct path to the ACME challenge file
        # This follows the standard .well-known/acme-challenge path
        challenge_file = Path(
            sep, "var", "tmp", "bunkerweb", "lets-encrypt", 
            ".well-known", "acme-challenge", token
        )
        
        debug_log(LOGGER, f"Challenge file path: {challenge_file}")
        debug_log(LOGGER, f"Token filename: {token}")
        debug_log(LOGGER, 
            "Checking if challenge file exists before cleanup")
        debug_log(LOGGER, 
            f"File exists before cleanup: {challenge_file.exists()}")
        if challenge_file.exists():
            debug_log(LOGGER, 
                f"File size: {challenge_file.stat().st_size} bytes")
        
        # Remove the challenge file if it exists
        # missing_ok=True prevents errors if file doesn't exist
        challenge_file.unlink(missing_ok=True)
        
        debug_log(LOGGER, "Challenge file unlink operation completed")
        debug_log(LOGGER, 
            f"File exists after cleanup: {challenge_file.exists()}")
        debug_log(LOGGER, "Local challenge file cleanup completed successfully")
        debug_log(LOGGER, 
            "Challenge is no longer accessible to Let's Encrypt")
        
        LOGGER.info(f"Challenge file removed: {challenge_file}")

except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-cleanup.py:\n{e}")
    
    debug_log(LOGGER, "Full exception traceback logged above")
    debug_log(LOGGER, "Cleanup process failed due to exception")
    debug_log(LOGGER, "Some challenge files may remain uncleaned")

debug_log(LOGGER, 
    f"ACME HTTP challenge cleanup completed with status: {status}")
if status == 0:
    debug_log(LOGGER, "Cleanup completed successfully")
    debug_log(LOGGER, "All challenge files have been removed")
else:
    debug_log(LOGGER, 
        "Cleanup encountered errors - some files may remain")

sys_exit(status)