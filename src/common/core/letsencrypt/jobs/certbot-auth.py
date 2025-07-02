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


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


try:
    # Get environment variables for ACME HTTP challenge
    # CERTBOT_TOKEN: The filename for the challenge file
    # CERTBOT_VALIDATION: The content to write to the challenge file
    token = getenv("CERTBOT_TOKEN", "")
    validation = getenv("CERTBOT_VALIDATION", "")
    
    debug_log(LOGGER, "ACME HTTP challenge authentication started")
    debug_log(LOGGER, f"Token: {token[:10] if token else 'None'}...")
    debug_log(LOGGER, 
        f"Validation length: {len(validation) if validation else 0} chars")
    debug_log(LOGGER, "Checking for required environment variables")
    debug_log(LOGGER, f"CERTBOT_TOKEN exists: {bool(token)}")
    debug_log(LOGGER, f"CERTBOT_VALIDATION exists: {bool(validation)}")
    
    # Detect the current BunkerWeb integration type
    # This determines how we handle the challenge deployment
    integration = get_integration()
    
    debug_log(LOGGER, f"Integration detection completed: {integration}")
    debug_log(LOGGER, 
        "Determining challenge deployment method based on integration")

    LOGGER.info(f"Detected {integration} integration")

    # Cluster case: Docker, Swarm, Kubernetes, Autoconf
    # For cluster deployments, we need to distribute the challenge
    # to all instances via the BunkerWeb API
    if integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        debug_log(LOGGER, 
            "Cluster integration detected, initializing database connection")
        debug_log(LOGGER, 
            "Will distribute challenge to all cluster instances via API")
        
        # Initialize database connection to get list of instances
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

        # Get all active BunkerWeb instances from the database
        instances = db.get_instances()
        
        debug_log(LOGGER, f"Retrieved {len(instances)} instances from database")
        debug_log(LOGGER, "Instance details:")
        for i, instance in enumerate(instances):
            debug_log(LOGGER, 
                f"  Instance {i+1}: {instance['hostname']}:"
                f"{instance['port']} (server: "
                f"{instance.get('server_name', 'N/A')})")
        debug_log(LOGGER, 
            "Preparing to send challenge data to each instance")

        LOGGER.info(f"Sending challenge to {len(instances)} instances")
        
        # Send challenge to each instance via API
        for instance in instances:
            debug_log(LOGGER, 
                f"Processing instance: {instance['hostname']}:"
                f"{instance['port']}")
            debug_log(LOGGER, 
                f"Server name: {instance.get('server_name', 'N/A')}")
            debug_log(LOGGER, "Creating API client for this instance")
            
            # Create API client for this instance
            api = API(
                f"http://{instance['hostname']}:{instance['port']}", 
                host=instance["server_name"]
            )
            
            debug_log(LOGGER, f"API endpoint: {api.endpoint}")
            debug_log(LOGGER, "Preparing challenge data payload")
            debug_log(LOGGER, f"Token: {token[:10]}... (truncated)")
            debug_log(LOGGER, 
                f"Validation length: {len(validation)} characters")
            
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
                debug_log(LOGGER, f"API request failed with error: {err}")
                debug_log(LOGGER, 
                    "This instance will not receive the challenge")
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
                    "Challenge deployment failed for this instance")
            else:
                LOGGER.info(
                    f"Successfully sent API request to "
                    f"{api.endpoint}/lets-encrypt/challenge"
                )
                debug_log(LOGGER, f"HTTP status code: {status_code}")
                debug_log(LOGGER, 
                    "Challenge successfully deployed to instance")
                debug_log(LOGGER, 
                    f"Instance can now serve challenge at "
                    f"/.well-known/acme-challenge/{token}")

    # Linux case: Standalone installation
    # For standalone Linux installations, we write the challenge
    # file directly to the local filesystem
    else:
        debug_log(LOGGER, "Standalone Linux integration detected")
        debug_log(LOGGER, 
            "Writing challenge file directly to local filesystem")
        debug_log(LOGGER, 
            "No API distribution needed for standalone mode")
        
        # Create the ACME challenge directory structure
        # This follows the standard .well-known/acme-challenge path
        root_dir = Path(
            sep, "var", "tmp", "bunkerweb", "lets-encrypt", 
            ".well-known", "acme-challenge"
        )
        
        debug_log(LOGGER, f"Challenge directory path: {root_dir}")
        debug_log(LOGGER, 
            "Creating directory structure if it doesn't exist")
        debug_log(LOGGER, 
            "Directory will be created with parents=True, exist_ok=True")
        
        # Create directory structure with appropriate permissions
        root_dir.mkdir(parents=True, exist_ok=True)
        
        debug_log(LOGGER, "Directory structure created successfully")
        debug_log(LOGGER, f"Directory exists: {root_dir.exists()}")
        debug_log(LOGGER, f"Directory is writable: {root_dir.is_dir()}")
        
        # Write the challenge validation content to the token file
        challenge_file = root_dir.joinpath(token)
        
        debug_log(LOGGER, f"Challenge file path: {challenge_file}")
        debug_log(LOGGER, f"Token filename: {token}")
        debug_log(LOGGER, 
            f"Validation content length: {len(validation)} bytes")
        debug_log(LOGGER, "Writing validation content to challenge file")
        
        challenge_file.write_text(validation, encoding="utf-8")
        
        debug_log(LOGGER, "Challenge file written successfully")
        debug_log(LOGGER, f"File exists: {challenge_file.exists()}")
        debug_log(LOGGER, 
            f"File size: {challenge_file.stat().st_size} bytes")
        debug_log(LOGGER, "Let's Encrypt can now access the challenge file")
        
        LOGGER.info(f"Challenge file created at {challenge_file}")

except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-auth.py:\n{e}")
    
    debug_log(LOGGER, "Full exception traceback logged above")
    debug_log(LOGGER, "Authentication process failed due to exception")
    debug_log(LOGGER, "Let's Encrypt challenge will not be available")

debug_log(LOGGER, 
    f"ACME HTTP challenge authentication completed with status: {status}")
if status == 0:
    debug_log(LOGGER, "Authentication completed successfully")
    debug_log(LOGGER, "Let's Encrypt can now access the challenge")
else:
    debug_log(LOGGER, 
        "Authentication failed - challenge may not be accessible")

sys_exit(status)