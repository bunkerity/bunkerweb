#!/usr/bin/env python3

from os import sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore
from mmdb import COUNTRY, update_runtime_mmdb  # type: ignore

LOGGER = getLogger("JOBS.MMDB-COUNTRY")
status = 0

try:
    JOB = Job(LOGGER, __file__)
    status = update_runtime_mmdb(COUNTRY, JOB, Path(sep, "var", "tmp", "bunkerweb", "country.mmdb"), logger=LOGGER)
except Exception as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running mmdb-country.py :\n{e}")

sys_exit(status)
