#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from jobs import Job  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("FAILOVER-BACKUP", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Restoring the backup failover configuration
    JOB = Job(LOGGER)
except:
    status = 2
    LOGGER.error(f"Exception while running failover-backup.py :\n{format_exc()}")

sys_exit(status)
