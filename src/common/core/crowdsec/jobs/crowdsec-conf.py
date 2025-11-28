#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from jinja2 import Environment, FileSystemLoader
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("CROWDSEC")
PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "crowdsec")
status = 0

try:
    # Check if at least a server has CrowdSec activated
    cs_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "www.example.com").strip().split(" "):
            if getenv(f"{first_server}_USE_CROWDSEC", "no") == "yes":
                cs_activated = True
                break
    # Singlesite case
    elif getenv("USE_CROWDSEC", "no") == "yes":
        cs_activated = True

    if not cs_activated:
        LOGGER.info("CrowdSec is not activated, skipping job...")
        sys_exit(status)

    JOB = Job(LOGGER, __file__)

    # Generate content
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

    # Update db
    cached, err = JOB.cache_file("crowdsec.conf", content)
    if not cached:
        LOGGER.error(f"Error while caching crowdsec.conf file : {err}")

    # Done
    LOGGER.info("CrowdSec configuration successfully generated")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running crowdsec-init.py :\n{e}")

sys_exit(status)
