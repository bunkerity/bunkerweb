#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore

LOGGER = getLogger("MODSECURITY.CORERULESET.NIGHTLY")
status = 0

try:
    # * Check if we're using the nightly version of the Core Rule Set (CRS)
    use_nightly_crs = False

    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "www.example.com").split():
            if first_server and getenv(f"{first_server}_MODSECURITY_CRS_VERSION", "4") == "nightly":
                use_nightly_crs = True
                break
    elif getenv("MODSECURITY_CRS_VERSION", "4") == "nightly":
        use_nightly_crs = True

    if not use_nightly_crs:
        sys_exit(0)

    LOGGER.warning(
        "MODSECURITY_CRS_VERSION is set to 'nightly' which is deprecated. "
        "The nightly release of the OWASP Core Rule Set has been discontinued. "
        "CRS v4 will be used instead. Please update your configuration to use MODSECURITY_CRS_VERSION=4."
    )
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running coreruleset-nightly.py :\n{e}")

sys_exit(status)
