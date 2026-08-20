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
from common_utils import bytes_hash  # type: ignore
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

            # Exiting 1 is the ONLY thing that ships these files. The worker pushes
            # /var/cache/bunkerweb to every instance and reloads them exactly when a job exits 1
            # (`if ret == 1 and apis:`, src/worker/tasks.py:426); `plugin.json`'s "reload" flag is
            # persisted but never consulted for that decision. It matters more here than for the
            # other cache-shipping plugins: the bouncers are built once, in init_by_lua
            # (crowdsec.lua), and only a reload re-runs that -- so a configuration that never
            # triggers one is never applied at all. This job is also `every: once`, so unlike the
            # hourly downloaders it gets no second attempt to piggyback on another job's push.
            new_hash = bytes_hash(content)
            if new_hash == JOB.cache_hash(CONF_NAME, service_id=service):
                LOGGER.info(f"{CONF_NAME} for {service or 'the whole instance'} is unchanged, reload is not needed")
                continue

            cached, err = JOB.cache_file(CONF_NAME, content, service_id=service, checksum=new_hash)
            if not cached:
                status = 2
                LOGGER.error(f"Error while caching {CONF_NAME} file for {service or 'the whole instance'} : {err}")
            elif status == 0:
                status = 1

    # Drop configurations left behind by services that no longer use CrowdSec, and the
    # instance-wide one written by older versions in multisite. They hold the API key.
    #
    # In multisite the service lists are built from SERVER_NAME, so empty on both sides means the
    # environment named nothing at all: a partial or racing job environment produces that exactly
    # like a real "nothing configured" does, and there is no evidence of what is stale. Sweeping
    # then would delete every service's configuration on the strength of a missing variable.
    # Outside multisite the instance is the single service and ([], []) is determinate: CrowdSec
    # is off, and the rendered configuration with its API key is precisely what must go.
    multisite = getenv("MULTISITE", "no") == "yes"
    stale = set(disabled)

    if services or disabled or not multisite:
        if services != [""]:
            stale.add("")
        # `disabled` only names services SERVER_NAME still lists, but Job() restores a cached file
        # for every service_id the database holds, so one dropped from SERVER_NAME entirely would
        # be put back on every run and never swept. Sweep by what is on disk instead.
        if JOB.job_path.is_dir():
            for entry in JOB.job_path.iterdir():
                if entry.is_dir() and entry.name not in services:
                    stale.add(entry.name)

    for service in sorted(stale):
        if JOB.job_path.joinpath(service, CONF_NAME).is_file():
            deleted, err = JOB.del_cache(CONF_NAME, service_id=service)
            if not deleted:
                LOGGER.warning(f"Couldn't remove stale {CONF_NAME} for {service or 'the whole instance'} : {err}")
            elif status == 0:
                # A removal has to reach the instances too: until a push happens they keep the
                # deleted configuration on disk and the bouncer keeps checking that service.
                status = 1

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
