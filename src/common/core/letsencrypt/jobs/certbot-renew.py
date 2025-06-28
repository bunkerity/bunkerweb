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
        LOGGER.debug("Checking if Let's Encrypt is enabled")
    
    use_letsencrypt = False
    multisite_mode = getenv("MULTISITE", "no") == "yes"
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Multisite mode: {multisite_mode}")

    # Single-site mode: Check global AUTO_LETS_ENCRYPT setting
    if not multisite_mode:
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Single-site mode - AUTO_LETS_ENCRYPT: {use_letsencrypt}")
    
    # Multi-site mode: Check per-server AUTO_LETS_ENCRYPT settings
    else:
        server_names = getenv("SERVER_NAME", "www.example.com").split(" ")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Multi-site mode - checking {len(server_names)} servers")
            LOGGER.debug(f"Server names: {server_names}")
        
        # Check if any server has Let's Encrypt enabled
        for i, first_server in enumerate(server_names):
            if first_server:
                server_le_enabled = getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes"
                
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(
                        f"Server {i+1} ({first_server}): "
                        f"AUTO_LETS_ENCRYPT = {server_le_enabled}"
                    )
                
                if server_le_enabled:
                    use_letsencrypt = True
                    break

    # Exit early if Let's Encrypt is not configured
    if not use_letsencrypt:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Let's Encrypt not enabled, exiting renewal process")
        LOGGER.info("Let's Encrypt is not activated, skipping renew...")
        sys_exit(0)

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Let's Encrypt is enabled, proceeding with renewal")

    # Initialize job handler for caching operations
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Initializing job handler")
    
    JOB = Job(LOGGER, __file__)

    # Set up environment variables for certbot execution
    # These control paths, timeouts, and configuration testing behavior
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Setting up environment for certbot execution")
    
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
    if getenv("DATABASE_URI"):
        env["DATABASE_URI"] = getenv("DATABASE_URI")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Environment configuration:")
        LOGGER.debug(f"  PATH: {env['PATH'][:100]}..." if len(env['PATH']) > 100 else f"  PATH: {env['PATH']}")
        LOGGER.debug(f"  PYTHONPATH: {env['PYTHONPATH'][:100]}..." if len(env['PYTHONPATH']) > 100 else f"  PYTHONPATH: {env['PYTHONPATH']}")
        LOGGER.debug(f"  RELOAD_MIN_TIMEOUT: {env['RELOAD_MIN_TIMEOUT']}")
        LOGGER.debug(f"  DISABLE_CONFIGURATION_TESTING: {env['DISABLE_CONFIGURATION_TESTING']}")
        LOGGER.debug(f"  DATABASE_URI configured: {'Yes' if getenv('DATABASE_URI') else 'No'}")

    # Construct certbot renew command with appropriate options
    # --no-random-sleep-on-renew: Prevents random delays in scheduled runs
    # Paths are configured to use BunkerWeb's certificate storage locations
    command = [
        CERTBOT_BIN,
        "renew",
        "--no-random-sleep-on-renew",
        "--config-dir",
        DATA_PATH.as_posix(),
        "--work-dir",
        WORK_DIR,
        "--logs-dir",
        LOGS_DIR,
    ]
    
    # Add verbose flag if debug logging is enabled
    if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG":
        command.append("-v")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Debug mode enabled, adding verbose flag to certbot")

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Certbot command: {' '.join(command)}")
        LOGGER.debug(f"Working directory: {WORK_DIR}")
        LOGGER.debug(f"Config directory: {DATA_PATH.as_posix()}")
        LOGGER.debug(f"Logs directory: {LOGS_DIR}")

    LOGGER.info("Starting certificate renewal process")

    # Execute certbot renew command
    # Process output is captured and logged through our logger
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Executing certbot renew command")
    
    process = Popen(
        command,
        stdin=DEVNULL,
        stderr=PIPE,
        universal_newlines=True,
        env=env,
    )
    
    # Stream certbot output to our logger in real-time
    # This ensures all certbot messages are captured in BunkerWeb logs
    line_count = 0
    while process.poll() is None:
        if process.stderr:
            for line in process.stderr:
                line_count += 1
                LOGGER_CERTBOT.info(line.strip())
                
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" and line_count % 10 == 0:
                    LOGGER.debug(f"Processed {line_count} certbot output lines")

    # Wait for process completion and check return code
    final_return_code = process.returncode
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Certbot process completed with return code: {final_return_code}")
        LOGGER.debug(f"Total certbot output lines processed: {line_count}")

    # Handle renewal results
    if final_return_code != 0:
        status = 2
        LOGGER.error("Certificates renewal failed")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Renewal process failed, certificate data will not be cached")
    else:
        LOGGER.info("Certificate renewal completed successfully")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Renewal process succeeded, proceeding to cache certificate data")

    # Save Let's Encrypt certificate data to database cache
    # This ensures certificate data is available for distribution to cluster nodes
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Checking if certificate data directory exists")
        LOGGER.debug(f"Data path: {DATA_PATH}")
        LOGGER.debug(f"Directory exists: {DATA_PATH.is_dir()}")
        if DATA_PATH.is_dir():
            dir_contents = list(DATA_PATH.iterdir())
            LOGGER.debug(f"Directory contents count: {len(dir_contents)}")
    
    # Only cache if directory exists and contains files
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Caching certificate data to database")
        
        cached, err = JOB.cache_dir(DATA_PATH)
        if not cached:
            LOGGER.error(
                f"Error while saving Let's Encrypt data to db cache: {err}"
            )
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Cache operation failed with error: {err}")
        else:
            LOGGER.info("Successfully saved Let's Encrypt data to db cache")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Certificate data successfully cached to database")
    else:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("No certificate data to cache (directory empty or missing)")
        LOGGER.warning("No certificate data found to cache")

except SystemExit as e:
    status = e.code
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Script exiting with SystemExit code: {e.code}")
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-renew.py:\n{e}")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Full exception traceback logged above")
        LOGGER.debug("Setting exit status to 2 due to unexpected exception")

if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    LOGGER.debug(f"Certificate renewal process completed with status: {status}")

sys_exit(status)