#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
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
        LOGGER.debug(f"ACME HTTP challenge authentication started")
        LOGGER.debug(f"Token: {token[:10] if token else 'None'}...")
        LOGGER.debug(f"Validation length: {len(validation) if validation else 0} chars")
    
    # Detect the current BunkerWeb integration type
    # This determines how we handle the challenge deployment
    integration = get_integration()
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Integration detection completed: {integration}")

    LOGGER.info(f"Detected {integration} integration")

    # Cluster case: Docker, Swarm, Kubernetes, Autoconf
    # For cluster deployments, we need to distribute the challenge
    # to all instances via the BunkerWeb API
    if integration in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Cluster integration detected, initializing database connection")
        
        # Initialize database connection to get list of instances
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

        # Get all active BunkerWeb instances from the database
        instances = db.get_instances()
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Retrieved {len(instances)} instances from database")
            for i, instance in enumerate(instances):
                LOGGER.debug(
                    f"Instance {i+1}: {instance['hostname']}:"
                    f"{instance['port']} (server: {instance.get('server_name', 'N/A')})"
                )

        LOGGER.info(f"Sending challenge to {len(instances)} instances")
        
        # Send challenge to each instance via API
        for instance in instances:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(
                    f"Sending challenge to instance: "
                    f"{instance['hostname']}:{instance['port']}"
                )
            
            # Create API client for this instance
            api = API(
                f"http://{instance['hostname']}:{instance['port']}", 
                host=instance["server_name"]
            )
            
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
            elif status_code != 200:
                status = 1
                LOGGER.error(
                    f"Error while sending API request to "
                    f"{api.endpoint}/lets-encrypt/challenge: "
                    f"status = {resp['status']}, msg = {resp['msg']}"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"API response details: {resp}")
            else:
                LOGGER.info(
                    f"Successfully sent API request to "
                    f"{api.endpoint}/lets-encrypt/challenge"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(
                        f"Challenge successfully deployed to "
                        f"{instance['hostname']}:{instance['port']}"
                    )

    # Linux case: Standalone installation
    # For standalone Linux installations, we write the challenge
    # file directly to the local filesystem
    else:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(
                "Standalone Linux integration detected, "
                "writing challenge file locally"
            )
        
        # Create the ACME challenge directory structure
        # This follows the standard .well-known/acme-challenge path
        root_dir = Path(
            sep, "var", "tmp", "bunkerweb", "lets-encrypt", 
            ".well-known", "acme-challenge"
        )
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Creating challenge directory: {root_dir}")
        
        # Create directory structure with appropriate permissions
        root_dir.mkdir(parents=True, exist_ok=True)
        
        # Write the challenge validation content to the token file
        challenge_file = root_dir.joinpath(token)
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Writing challenge file: {challenge_file}")
            LOGGER.debug(f"Challenge file content length: {len(validation)} bytes")
        
        challenge_file.write_text(validation, encoding="utf-8")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Challenge file written successfully")
        
        LOGGER.info(f"Challenge file created at {challenge_file}")

except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-auth.py:\n{e}")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Full exception traceback logged above")

if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    LOGGER.debug(f"ACME HTTP challenge authentication completed with status: {status}")

sys_exit(status)