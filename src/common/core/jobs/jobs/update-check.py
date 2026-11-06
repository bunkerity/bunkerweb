#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from json import dumps, loads
from os import sep
from os.path import join
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from unicodedata import east_asian_width

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from packaging.version import Version
from requests import get
from requests.exceptions import ConnectionError, RequestException

from common_utils import fetch_bunkerweb_releases, get_version, is_newer_version_available, normalize_bunkerweb_version, pick_latest_line_release  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("UPDATE-CHECK")
status = 0

try:
    JOB = Job(LOGGER, __file__)

    def get_latest_stable_release():
        # Try cache first to respect a 1-hour cooldown with metadata, similar to mmdb-asn job
        job_cache = JOB.get_cache("latest_release.json", with_info=True, with_data=True)
        if isinstance(job_cache, dict):
            last_update = job_cache.get("last_update")
            if last_update and datetime.now().astimezone().timestamp() - last_update < timedelta(hours=1).total_seconds():
                LOGGER.info("Using cached GitHub release (fresh < 1h)")
                data = job_cache.get("data") or b"{}"
                with suppress(BaseException):
                    return loads(data)

        max_retries = 3
        retry_count = 0
        while True:
            try:
                releases = fetch_bunkerweb_releases(get)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)
            except RequestException:
                LOGGER.debug(format_exc())
                # Best-effort fallback to cached info (may be stale)
                if isinstance(job_cache, dict) and job_cache.get("data"):
                    LOGGER.warning("GitHub API error, falling back to cached release info")
                    with suppress(BaseException):
                        return loads(job_cache.get("data") or b"{}")
                raise

        current_version = get_version()
        latest = pick_latest_line_release(releases, current_version)

        # If no stable release found, fallback to cache if available
        if latest is None:
            if isinstance(job_cache, dict) and job_cache.get("data"):
                LOGGER.warning("No stable release found from API, using cached info")
                with suppress(BaseException):
                    return loads(job_cache.get("data") or b"{}")
            return None

        # A newer line (e.g. 1.7.x while on 1.6) is not an update: only point at the upgrade guide
        with suppress(BaseException):
            overall = pick_latest_line_release(releases, "unknown")
            if overall and overall is not latest:
                current_parsed = Version(normalize_bunkerweb_version(current_version))
                LOGGER.info(
                    f"BunkerWeb {overall['tag_name'].removeprefix('v')} is available on a newer release line, "
                    f"see https://docs.bunkerweb.io/{current_parsed.major}.{current_parsed.minor}/upgrading/"
                )

        # Cache the latest stable release for 1 hour to avoid rate limits
        with suppress(BaseException):
            JOB.cache_file("latest_release.json", dumps(latest).encode())

        return latest

    try:
        latest_release = get_latest_stable_release()
    except RequestException:
        LOGGER.debug(format_exc())
        LOGGER.warning("Could not reach the GitHub API to check for a newer release, skipping this run")
        sys_exit(0)

    if not latest_release:
        status = 2  # Exit 1 means changed data and triggers a fleet reload.
        LOGGER.error("Failed to fetch latest release information")
        sys_exit(status)

    current_version = get_version()
    latest_version = latest_release["tag_name"].removeprefix("v")

    if is_newer_version_available(current_version, latest_version):
        latest_version_text = f"\033[1;92m{latest_version}\033[0m"
        current_version_text = f"\033[1;93m{current_version}\033[0m"
        release_notes_url = f"https://github.com/bunkerity/bunkerweb/releases/v{latest_version}"
        release_notes_url_text = f"\033[4;94m{release_notes_url}\033[0m"

        alert_message = "\033[1;97m🚨  A NEW VERSION OF BUNKERWEB IS AVAILABLE!  🚨\033[0m"
        latest_version_line = f"\033[1;97mLatest Version: {latest_version_text}\033[0m"
        current_version_line = f"\033[1;97mCurrent Version: {current_version_text}\033[0m"
        release_notes_url_line = f"\033[1;97mRelease Notes: {release_notes_url_text}\033[0m"

        ansi_pattern = re_compile(r"\x1b\[[0-9;]*[a-zA-Z]")

        def display_width(text: str) -> int:
            clean = ansi_pattern.sub("", text)
            return sum(2 if east_asian_width(c) in ("F", "W") else 1 for c in clean)

        def pad_center(text: str, target_width: int) -> str:
            pad = target_width - display_width(text)
            left = pad // 2
            right = pad - left
            return f"{' ' * left}{text}{' ' * right}"

        content_lines = [alert_message, latest_version_line, current_version_line, release_notes_url_line]
        max_width = max(display_width(line) for line in content_lines)

        box_width = max_width + 4
        border = f"\033[1;91m+{'—' * box_width}+\033[0m"
        empty_row = f"\033[1;91m|{' ' * box_width}|\033[0m"

        LOGGER.warning(
            (
                f"\n{border}\n"
                f"{empty_row}\n"
                f"\033[1;91m|\033[0m  {pad_center(alert_message, max_width)}  \033[1;91m|\033[0m\n"
                f"{empty_row}\n"
                f"\033[1;91m|\033[0m  {pad_center(latest_version_line, max_width)}  \033[1;91m|\033[0m\n"
                f"\033[1;91m|\033[0m  {pad_center(current_version_line, max_width)}  \033[1;91m|\033[0m\n"
                f"{empty_row}\n"
                f"\033[1;91m|\033[0m  {pad_center(release_notes_url_line, max_width)}  \033[1;91m|\033[0m\n"
                f"{empty_row}\n"
                f"{border}"
            )
        )
    else:
        LOGGER.info(f"No newer stable version available (current: {current_version}, latest stable: {latest_version})")
except SystemExit:
    raise
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running update-check.py :\n{e}")

sys_exit(status)
