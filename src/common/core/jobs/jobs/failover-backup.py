#!/usr/bin/env python3

from os import sep
from os.path import join
from sys import exit as sys_exit, path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from jobs import Job  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("FAILOVER-BACKUP")
status = 0

try:
    # Restoring the backup failover configuration
    JOB = Job(LOGGER, __file__)
except BaseException as e:
    status = 2
    LOGGER.error(f"Exception while running failover-backup.py :\n{e}")

sys_exit(status)
