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

LOGGER = getLogger("DB.CLEANUP-EXCESS-JOBS-RUNS")
status = 0

try:
    DB = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
    ret = DB.cleanup_jobs_runs_excess(int(getenv("DATABASE_MAX_JOBS_RUNS", "10000")))
    if not ret.startswith("Removed"):
        LOGGER.error(ret)
        sys_exit(1)
    LOGGER.info(ret)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running cleanup-excess-jobs-runs.py :\n{e}")

sys_exit(status)
