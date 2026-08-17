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

    # Built before the no-service exit: disabling CrowdSec on the last service is exactly when
    # the stale cleanup below has to run, and exiting first left every rendered configuration,
    # API key included, on disk forever.
    JOB = Job(LOGGER, __file__)

    if services:
        template = Environment(loader=FileSystemLoader(PLUGIN_PATH.joinpath("misc"))).get_template(CONF_NAME)

        for service in services:
            content = template.render(**render_variables(getenv, service)).encode()
            cached, err = JOB.cache_file(CONF_NAME, content, service_id=service)
            if not cached:
                status = 2
                LOGGER.error(f"Error while caching {CONF_NAME} file for {service or 'the whole instance'} : {err}")

    # Drop configurations left behind by services that no longer use CrowdSec, and the
    # instance-wide one written by older versions in multisite. They hold the API key.
    stale = set(disabled)
    if services != [""]:
        stale.add("")
    # `disabled` only names services SERVER_NAME still lists, but Job() restores a cached file for
    # every service_id the database holds, so one dropped from SERVER_NAME entirely would be put
    # back on every run and never swept. Sweep by what is actually on disk instead.
    # Both lists empty means the job environment named no service at all, which happens on a
    # partial or racing environment as readily as on a real "nothing configured". There is no
    # evidence of what is stale then, so sweeping the disk would delete every service's
    # configuration on the strength of a missing variable.
    if (services or disabled) and JOB.job_path.is_dir():
        for entry in JOB.job_path.iterdir():
            if entry.is_dir() and entry.name not in services:
                stale.add(entry.name)

    for service in sorted(stale):
        if JOB.job_path.joinpath(service, CONF_NAME).is_file():
            deleted, err = JOB.del_cache(CONF_NAME, service_id=service)
            if not deleted:
                LOGGER.warning(f"Couldn't remove stale {CONF_NAME} for {service or 'the whole instance'} : {err}")

    if not services:
        LOGGER.info("CrowdSec is not activated, skipping generation...")
    else:
        LOGGER.info(f"CrowdSec configuration successfully generated for {len(services)} service(s)")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running crowdsec-conf.py :\n{e}")

sys_exit(status)
