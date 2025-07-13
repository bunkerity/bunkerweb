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

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="crowdsec",
    log_file_path="/var/log/bunkerweb/crowdsec.log"
)

logger.debug("Debug mode enabled for crowdsec")

from jinja2 import Environment, FileSystemLoader
from jobs import Job  # type: ignore

PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "crowdsec")
status = 0

try:
    logger.debug("Starting crowdsec configuration generation")
    
    # Check if at least a server has CrowdSec activated
    cs_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        logger.debug("Checking multisite configuration")
        for first_server in getenv("SERVER_NAME", "www.example.com").strip().split(" "):
            if getenv(f"{first_server}_USE_CROWDSEC", "no") == "yes":
                cs_activated = True
                logger.debug(f"Crowdsec activated for server: {first_server}")
                break
    # Singlesite case
    elif getenv("USE_CROWDSEC", "no") == "yes":
        cs_activated = True
        logger.debug("Crowdsec activated for singlesite")

    if not cs_activated:
        logger.info("CrowdSec is not activated, skipping job...")
        sys_exit(status)

    JOB = Job(logger, __file__)

    # Generate content
    logger.debug("Rendering crowdsec.conf template")
    jinja_env = Environment(loader=FileSystemLoader(PLUGIN_PATH.joinpath("misc")))
    content = (
        jinja_env.get_template("crowdsec.conf")
        .render(
            CROWDSEC_API=getenv("CROWDSEC_API", "http://crowdsec:8080"),
            CROWDSEC_API_KEY=getenv("CROWDSEC_API_KEY", ""),
            CROWDSEC_MODE=getenv("CROWDSEC_MODE", "live"),
            CROWDSEC_ENABLE_INTERNAL=("true" if getenv("CROWDSEC_ENABLE_INTERNAL", "no") == "yes" else "false"),
            CROWDSEC_REQUEST_TIMEOUT=getenv("CROWDSEC_REQUEST_TIMEOUT", "1000"),
            CROWDSEC_EXCLUDE_LOCATION=getenv("CROWDSEC_EXCLUDE_LOCATION", ""),
            CROWDSEC_CACHE_EXPIRATION=getenv("CROWDSEC_CACHE_EXPIRATION", "1"),
            CROWDSEC_UPDATE_FREQUENCY=getenv("CROWDSEC_UPDATE_FREQUENCY", "10"),
            CROWDSEC_APPSEC_URL=getenv("CROWDSEC_APPSEC_URL", ""),
            CROWDSEC_APPSEC_FAILURE_ACTION=getenv("CROWDSEC_APPSEC_FAILURE_ACTION", "passthrough"),
            CROWDSEC_APPSEC_CONNECT_TIMEOUT=getenv("CROWDSEC_APPSEC_CONNECT_TIMEOUT", "100"),
            CROWDSEC_APPSEC_SEND_TIMEOUT=getenv("CROWDSEC_APPSEC_SEND_TIMEOUT", "100"),
            CROWDSEC_APPSEC_PROCESS_TIMEOUT=getenv("CROWDSEC_APPSEC_PROCESS_TIMEOUT", "500"),
            CROWDSEC_ALWAYS_SEND_TO_APPSEC=("true" if getenv("CROWDSEC_ALWAYS_SEND_TO_APPSEC", "no") == "yes" else "false"),
            CROWDSEC_APPSEC_SSL_VERIFY=("true" if getenv("CROWDSEC_APPSEC_SSL_VERIFY", "no") == "yes" else "false"),
        )
        .encode()
    )
    logger.debug(f"Generated configuration content size: {len(content)} bytes")

    # Update db
    cached, err = JOB.cache_file("crowdsec.conf", content)
    if not cached:
        logger.error(f"Error while caching crowdsec.conf file : {err}")
    else:
        logger.debug("Successfully cached crowdsec.conf file")

    # Done
    logger.info("CrowdSec configuration successfully generated")
except SystemExit as e:
    status = e.code
    logger.debug(f"SystemExit with code: {status}")
except BaseException as e:
    status = 2
    logger.exception("Exception while running crowdsec-conf.py")

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
