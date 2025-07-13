#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen
from sys import exit as sys_exit, path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger
from jobs import Job  # type: ignore

# Initialize bw_logger module for Let's Encrypt certificate renewal
logger = setup_logger(
    title="letsencrypt-certbot-renew",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-certbot-renew")

# Directory and binary paths for Let's Encrypt operations
LIB_PATH = Path(sep, "var", "lib", "bunkerweb", "letsencrypt")
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

# Additional logger for certbot subprocess output
logger_certbot = setup_logger(
    title="letsencrypt-certbot-renew-subprocess",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

status = 0

# Certificate storage and working directory paths
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

logger.debug(f"Certificate paths configured - DATA_PATH: {DATA_PATH}, WORK_DIR: {WORK_DIR}")

try:
    # Check if we're using let's encrypt across single or multi-site configurations
    logger.debug("Checking Let's Encrypt activation status")
    use_letsencrypt = False

    multisite_mode = getenv("MULTISITE", "no") == "no"
    logger.debug(f"Multisite mode: {not multisite_mode}")

    if not multisite_mode:
        # Single-site configuration check
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        logger.debug(f"Single-site Let's Encrypt status: {use_letsencrypt}")
    else:
        # Multi-site configuration check
        server_names = getenv("SERVER_NAME", "www.example.com").split(" ")
        logger.debug(f"Checking {len(server_names)} servers for Let's Encrypt activation")
        
        for i, first_server in enumerate(server_names):
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True
                logger.debug(f"Let's Encrypt enabled for server {i+1}/{len(server_names)}: {first_server}")
                break
            else:
                logger.debug(f"Let's Encrypt disabled for server {i+1}/{len(server_names)}: {first_server}")

    if not use_letsencrypt:
        logger.info("Let's Encrypt is not activated, skipping renew...")
        sys_exit(0)

    logger.info("Let's Encrypt is activated, proceeding with certificate renewal")

    # Initialize Job handler for cache management
    JOB = Job(logger, __file__)
    logger.debug("Job handler initialized for certificate renewal")

    # Setup environment variables for certbot execution
    env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "RELOAD_MIN_TIMEOUT": getenv("RELOAD_MIN_TIMEOUT", "5"),
        "DISABLE_CONFIGURATION_TESTING": getenv("DISABLE_CONFIGURATION_TESTING", "no").lower(),
    }
    env["PYTHONPATH"] = env["PYTHONPATH"] + (f":{DEPS_PATH}" if DEPS_PATH not in env["PYTHONPATH"] else "")
    if getenv("DATABASE_URI"):
        env["DATABASE_URI"] = getenv("DATABASE_URI")
    
    logger.debug(f"Environment configured for certbot - PYTHONPATH includes: {DEPS_PATH}")
    logger.debug(f"Reload timeout: {env['RELOAD_MIN_TIMEOUT']}, Config testing: {env['DISABLE_CONFIGURATION_TESTING']}")

    # Build certbot renew command with appropriate verbosity
    certbot_command = [
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
    debug_mode = getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG"
    if debug_mode:
        certbot_command.append("-v")
        logger.debug("Debug mode enabled, adding verbose flag to certbot")
    
    logger.debug(f"Certbot renewal command: {' '.join(certbot_command)}")

    # Execute certbot renewal process
    logger.info("Starting certificate renewal process")
    process = Popen(
        certbot_command,
        stdin=DEVNULL,
        stderr=PIPE,
        universal_newlines=True,
        env=env,
    )
    
    logger.debug(f"Certbot renewal process started with PID: {process.pid}")

    # Monitor certbot output and log it appropriately
    line_count = 0
    while process.poll() is None:
        if process.stderr:
            for line in process.stderr:
                line_count += 1
                logger_certbot.info(line.strip())
                # Log progress periodically in debug mode
                if debug_mode and line_count % 10 == 0:
                    logger.debug(f"Processed {line_count} lines of certbot output")

    exit_code = process.returncode
    logger.debug(f"Certbot renewal process completed with exit code: {exit_code}")

    if exit_code != 0:
        status = 2
        logger.error("Certificates renewal failed")
        logger.debug(f"Certbot failed with return code: {exit_code}")
    else:
        logger.info("Certificate renewal completed successfully")
        logger.debug(f"Processed total of {line_count} lines of certbot output")

    # Save Let's Encrypt data to database cache
    logger.debug("Checking if certificate data needs to be cached")
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        logger.debug(f"Certificate data directory exists with content: {DATA_PATH}")
        cached, err = JOB.cache_dir(DATA_PATH)
        if not cached:
            logger.error(f"Error while saving Let's Encrypt data to db cache : {err}")
        else:
            logger.info("Successfully saved Let's Encrypt data to db cache")
            logger.debug("Certificate data successfully cached to database")
    else:
        logger.debug("No certificate data directory found or directory is empty")
        logger.warning("No Let's Encrypt data to cache (directory missing or empty)")

except SystemExit as e:
    status = e.code
    logger.debug(f"Script exiting with SystemExit code: {e.code}")
except BaseException as e:
    status = 2
    logger.exception("Exception occurred while running certbot-renew.py")
    logger.error(f"Exception details: {type(e).__name__}: {e}")

logger.debug(f"Certificate renewal script completed with final status: {status}")
sys_exit(status)
