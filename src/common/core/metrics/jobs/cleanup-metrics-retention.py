#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("METRICS.CLEANUP-RETENTION")
status = 0

try:
    if getenv("METRICS_PERSIST_TO_DB", "yes") != "yes":
        LOGGER.info("METRICS_PERSIST_TO_DB is disabled, skipping retention cleanup...")
        sys_exit(0)

    DB = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

    by_age = DB.cleanup_metrics_by_age(int(getenv("METRICS_RETENTION_DAYS", "90")))
    if not by_age.startswith("Removed"):
        LOGGER.error(by_age)
        sys_exit(1)
    LOGGER.info(by_age)

    by_count = DB.cleanup_metrics_by_count(int(getenv("METRICS_RETENTION_MAX_ROWS", "1000000")))
    if not by_count.startswith("Removed"):
        LOGGER.error(by_count)
        sys_exit(1)
    LOGGER.info(by_count)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running cleanup-metrics-retention.py :\n{e}")

sys_exit(status)
