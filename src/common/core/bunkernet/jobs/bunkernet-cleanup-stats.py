#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("BUNKERNET.CLEANUP-STATS")
exit_status = 0

try:
    if getenv("USE_BUNKERNET_STATS", "yes") != "yes":
        LOGGER.info("USE_BUNKERNET_STATS is disabled, skipping BunkerNet stats cleanup...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    retention_days = getenv("BUNKERNET_STATS_RETENTION_DAYS", "30")
    days = int(retention_days) if retention_days.isdigit() and int(retention_days) > 0 else 30

    message = JOB.db.ext("bunkernet").cleanup_bunkernet_by_age(days)
    LOGGER.info(message)
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running bunkernet-cleanup-stats.py :\n{e}")

sys_exit(exit_status)
