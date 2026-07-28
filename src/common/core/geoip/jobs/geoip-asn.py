#!/usr/bin/env python3

from os import sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

from geoip_utils import redact, run

LOGGER = getLogger("JOBS.GEOIP-ASN")

try:
    status = run("asn", LOGGER, Job(LOGGER, __file__))
except BaseException as e:
    # redact: a MaxMind failure carries the licence key inside the exception text
    LOGGER.debug(redact(format_exc()))
    LOGGER.error(f"Exception while running geoip-asn.py :\n{redact(str(e))}")
    status = 2

sys_exit(status)
