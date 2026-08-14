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

from crowdsec_conf_utils import get_services, render_variables

LOGGER = getLogger("CROWDSEC")
PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "crowdsec")
CONF_NAME = "crowdsec.conf"
status = 0

try:
    # CROWDSEC_* settings are per-service, so each activated service gets its own
    # rendered configuration under its own job cache service_id.
    services, disabled = get_services(getenv)

    if not services:
        LOGGER.info("CrowdSec is not activated, skipping job...")
        sys_exit(status)

    JOB = Job(LOGGER, __file__)

    template = Environment(loader=FileSystemLoader(PLUGIN_PATH.joinpath("misc"))).get_template(CONF_NAME)

    for service in services:
        content = template.render(**render_variables(getenv, service)).encode()
        cached, err = JOB.cache_file(CONF_NAME, content, service_id=service)
        if not cached:
            status = 2
            LOGGER.error(f"Error while caching {CONF_NAME} file for {service or 'the whole instance'} : {err}")

    # Drop configurations left behind by services that no longer use CrowdSec, and the
    # instance-wide one written by older versions in multisite. They hold the API key.
    stale = list(disabled)
    if services != [""]:
        stale.append("")
    for service in stale:
        if JOB.job_path.joinpath(service, CONF_NAME).is_file():
            deleted, err = JOB.del_cache(CONF_NAME, service_id=service)
            if not deleted:
                LOGGER.warning(f"Couldn't remove stale {CONF_NAME} for {service or 'the whole instance'} : {err}")

    LOGGER.info(f"CrowdSec configuration successfully generated for {len(services)} service(s)")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running crowdsec-conf.py :\n{e}")

sys_exit(status)
