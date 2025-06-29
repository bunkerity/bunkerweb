#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("LETS-ENCRYPT.renew")
LIB_PATH = Path(sep, "var", "lib", "bunkerweb", "letsencrypt")
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", 
                   "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT.renew.certbot")
status = 0

CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

try:
    # Determine if Let's Encrypt is enabled in the current configuration
    # This checks both single-site and multi-site deployment modes
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Starting Let's Encrypt certificate renewal process")
        LOGGER.debug("Checking if Let's Encrypt is enabled in configuration")
        LOGGER.debug("Will check both single-site and multi-site modes")
    
    use_letsencrypt = False
    multisite_mode = getenv("MULTISITE", "no") == "yes"
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Multisite mode detected: {multisite_mode}")
        LOGGER.debug("Determining which Let's Encrypt check method to use")

    # Single-site mode: Check global AUTO_LETS_ENCRYPT setting
    if not multisite_mode:
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Checking single-site mode configuration")
            LOGGER.debug(f"Global AUTO_LETS_ENCRYPT setting: {use_letsencrypt}")
            LOGGER.debug("Single setting controls all domains in this mode")
    
    # Multi-site mode: Check per-server AUTO_LETS_ENCRYPT settings
    else:
        server_names = getenv("SERVER_NAME", "www.example.com").split(" ")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Checking multi-site mode configuration")
            LOGGER.debug(f"Found {len(server_names)} configured servers")
            LOGGER.debug(f"Server list: {server_names}")
            LOGGER.debug("Checking each server for Let's Encrypt enablement")
        
        # Check if any server has Let's Encrypt enabled
        for i, first_server in enumerate(server_names):
            if first_server:
                server_le_enabled = getenv(f"{first_server}_AUTO_LETS_ENCRYPT", 
                                         "no") == "yes"
                
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(
                        f"Server {i+1} ({first_server}): "
                        f"AUTO_LETS_ENCRYPT = {server_le_enabled}"
                    )
                
                if server_le_enabled:
                    use_letsencrypt = True
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Found Let's Encrypt enabled on {first_server}")
                        LOGGER.debug("At least one server needs renewal - proceeding")
                    break

    # Exit early if Let's Encrypt is not configured
    if not use_letsencrypt:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Let's Encrypt not enabled on any servers")
            LOGGER.debug("No certificates to renew - exiting early")
            LOGGER.debug("Renewal process skipped entirely")
        LOGGER.info("Let's Encrypt is not activated, skipping renew...")
        sys_exit(0)

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Let's Encrypt is enabled - proceeding with renewal")
        LOGGER.debug("Will attempt to renew all existing certificates")

    # Initialize job handler for caching operations
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Initializing job handler for database operations")
        LOGGER.debug("Job handler manages certificate data caching")
    
    JOB = Job(LOGGER, __file__)

    # Set up environment variables for certbot execution
    # These control paths, timeouts, and configuration testing behavior
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Setting up environment for certbot execution")
        LOGGER.debug("Configuring paths and operational parameters")
    
    env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "RELOAD_MIN_TIMEOUT": getenv("RELOAD_MIN_TIMEOUT", "5"),
        "DISABLE_CONFIGURATION_TESTING": getenv(
            "DISABLE_CONFIGURATION_TESTING", "no"
        ).lower(),
    }
    
    # Ensure our Python dependencies are in the path
    env["PYTHONPATH"] = env["PYTHONPATH"] + (
        f":{DEPS_PATH}" if DEPS_PATH not in env["PYTHONPATH"] else ""
    )
    
    # Pass database URI if configured (for cluster deployments)
    database_uri = getenv("DATABASE_URI")
    if database_uri is not None:
        env["DATABASE_URI"] = database_uri
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Environment configuration for certbot:")
        path_display = (env['PATH'][:100] + "..." if len(env['PATH']) > 100 
                       else env['PATH'])
        pythonpath_display = (env['PYTHONPATH'][:100] + "..." 
                             if len(env['PYTHONPATH']) > 100 
                             else env['PYTHONPATH'])
        LOGGER.debug(f"  PATH: {path_display}")
        LOGGER.debug(f"  PYTHONPATH: {pythonpath_display}")
        LOGGER.debug(f"  RELOAD_MIN_TIMEOUT: {env['RELOAD_MIN_TIMEOUT']}")
        LOGGER.debug(f"  DISABLE_CONFIGURATION_TESTING: {env['DISABLE_CONFIGURATION_TESTING']}")
        LOGGER.debug(f"  DATABASE_URI configured: {'Yes' if database_uri else 'No'}")

    # Construct certbot renew command with appropriate options
    # --no-random-sleep-on-renew: Prevents random delays in scheduled runs
    # Paths are configured to use BunkerWeb's certificate storage locations
    command = [
        CERTBOT_BIN,
        "renew",
        "--no-random-sleep-on-renew",  # Disable random sleep for scheduled runs
        "--config-dir",
        DATA_PATH.as_posix(),  # Where certificates are stored
        "--work-dir",
        WORK_DIR,  # Temporary working directory
        "--logs-dir",
        LOGS_DIR,  # Log output directory
    ]
    
    # Add verbose flag if debug logging is enabled
    if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG":
        command.append("-v")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Debug mode enabled - adding verbose flag to certbot")
            LOGGER.debug("Certbot will provide detailed output")

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Certbot command configuration:")
        LOGGER.debug(f"  Command: {' '.join(command)}")
        LOGGER.debug(f"  Working directory: {WORK_DIR}")
        LOGGER.debug(f"  Config directory: {DATA_PATH.as_posix()}")
        LOGGER.debug(f"  Logs directory: {LOGS_DIR}")
        LOGGER.debug("Command will check all existing certificates for renewal")

    LOGGER.info("Starting certificate renewal process")

    # Execute certbot renew command
    # Process output is captured and logged through our logger
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Executing certbot renew command")
        LOGGER.debug("Will capture and relay all certbot output")
        LOGGER.debug("Process runs with isolated environment")
    
    process = Popen(
        command,
        stdin=DEVNULL,  # No input needed
        stderr=PIPE,    # Capture error output
        universal_newlines=True,  # Text mode
        env=env,        # Controlled environment
    )
    
    # Stream certbot output to our logger in real-time
    # This ensures all certbot messages are captured in BunkerWeb logs
    line_count = 0
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Starting real-time output capture from certbot")
    
    while process.poll() is None:
        if process.stderr:
            for line in process.stderr:
                line_count += 1
                LOGGER_CERTBOT.info(line.strip())
                
                if (getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" 
                    and line_count % 10 == 0):
                    LOGGER.debug(f"Processed {line_count} lines of certbot output")

    # Wait for process completion and check return code
    final_return_code = process.returncode
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Certbot process completed")
        LOGGER.debug(f"Final return code: {final_return_code}")
        LOGGER.debug(f"Total output lines processed: {line_count}")
        LOGGER.debug("Analyzing return code to determine success/failure")

    # Handle renewal results
    if final_return_code != 0:
        status = 2
        LOGGER.error("Certificates renewal failed")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Certbot returned non-zero exit code")
            LOGGER.debug("Certificate renewal process failed")
            LOGGER.debug("Will not cache certificate data due to failure")
    else:
        LOGGER.info("Certificate renewal completed successfully")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Certbot completed successfully")
            LOGGER.debug("All eligible certificates have been renewed")
            LOGGER.debug("Proceeding to cache updated certificate data")

    # Save Let's Encrypt certificate data to database cache
    # This ensures certificate data is available for distribution to cluster nodes
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Checking certificate data directory for caching")
        LOGGER.debug(f"Certificate data path: {DATA_PATH}")
        LOGGER.debug(f"Directory exists: {DATA_PATH.is_dir()}")
        if DATA_PATH.is_dir():
            dir_contents = list(DATA_PATH.iterdir())
            LOGGER.debug(f"Directory contains {len(dir_contents)} items")
            LOGGER.debug("Directory listing:")
            for item in dir_contents[:5]:  # Show first 5 items
                LOGGER.debug(f"  {item.name}")
            if len(dir_contents) > 5:
                LOGGER.debug(f"  ... and {len(dir_contents) - 5} more items")
    
    # Only cache if directory exists and contains files
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Certificate data found - proceeding with caching")
            LOGGER.debug("This will store certificates in database for cluster distribution")
        
        cached, err = JOB.cache_dir(DATA_PATH)
        if not cached:
            LOGGER.error(
                f"Error while saving Let's Encrypt data to db cache: {err}"
            )
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Cache operation failed with error: {err}")
                LOGGER.debug("Certificates renewed but not cached for distribution")
        else:
            LOGGER.info("Successfully saved Let's Encrypt data to db cache")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Certificate data successfully cached to database")
                LOGGER.debug("Cached certificates available for cluster distribution")
    else:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("No certificate data directory found or directory empty")
            LOGGER.debug("This may be normal if no certificates needed renewal")
        LOGGER.warning("No certificate data found to cache")

except SystemExit as e:
    status = e.code
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Script exiting via SystemExit with code: {e.code}")
        LOGGER.debug("This is typically a normal exit condition")
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-renew.py:\n{e}")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Unexpected exception occurred during renewal")
        LOGGER.debug("Full exception traceback logged above")
        LOGGER.debug("Setting exit status to 2 due to unexpected exception")
        LOGGER.debug("Renewal process aborted due to error")

if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    LOGGER.debug(f"Certificate renewal process completed with final status: {status}")
    if status == 0:
        LOGGER.debug("Renewal process completed successfully")
        LOGGER.debug("All certificates are up to date")
    elif status == 2:
        LOGGER.debug("Renewal process failed")
        LOGGER.debug("Manual intervention may be required")
    else:
        LOGGER.debug(f"Renewal completed with status {status}")

sys_exit(status)