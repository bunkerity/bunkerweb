#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timedelta
from json import dumps, loads
from os import sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from requests.exceptions import ConnectionError, RequestException

from common_utils import fetch_bunkerweb_releases, get_version, is_newer_version_available, pick_latest_line_release  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("UPDATE-CHECK")
status = 0

try:
    JOB = Job(LOGGER, __file__)
    current_version = get_version()

    def get_latest_stable_release():
        # Try cache first to respect a 1-hour cooldown with metadata, similar to mmdb-asn job
        job_cache = JOB.get_cache("latest_release.json", with_info=True, with_data=True)
        cached = None
        if isinstance(job_cache, dict):
            with suppress(BaseException):
                cached = pick_latest_line_release([loads(job_cache.get("data") or b"{}")], current_version)
            last_update = job_cache.get("last_update")
            if cached and last_update and datetime.now().astimezone().timestamp() - last_update < timedelta(hours=1).total_seconds():
                LOGGER.info("Using cached GitHub release (fresh < 1h)")
                return cached

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
                # Best-effort fallback to eligible cached info (may be stale)
                if cached:
                    LOGGER.warning("GitHub API error, falling back to cached release info")
                    return cached
                raise

        latest = pick_latest_line_release(releases, current_version)

        # If no eligible release is listed, fall back to eligible cache if available
        if latest is None:
            if cached:
                LOGGER.warning("No eligible release found from API, using cached info")
                return cached
            return None

        overall = pick_latest_line_release(releases, "unknown")
        if overall and pick_latest_line_release([overall], current_version) is None and is_newer_version_available(current_version, overall["tag_name"]):
            line = ".".join(current_version.strip().lower().removeprefix("v").split(".")[:2])
            LOGGER.info(
                f"BunkerWeb {overall['tag_name'].removeprefix('v')} is available on a newer release line, " f"see https://docs.bunkerweb.io/{line}/upgrading/"
            )

        # Cache the selected release for 1 hour to avoid rate limits
        with suppress(BaseException):
            JOB.cache_file("latest_release.json", dumps(latest).encode())

        return latest

    try:
        latest_release = get_latest_stable_release()
    except RequestException:
        # A transient GitHub failure (rate limit, outage, no route) is expected and
        # non-actionable: a missed check is not a job failure, and the next run retries.
        LOGGER.debug(format_exc())
        LOGGER.warning("Could not reach the GitHub API to check for a newer release, skipping this run")
        sys_exit(0)

    if not latest_release:
        # 2, not 1: in the job contract 1 means "changed, ship the cache and reload the fleet"
        # (src/worker/tasks.py:426), and `success = ret in (0, 1)` (:398) would also record this
        # failure as a success. A failure must do neither.
        status = 2
        LOGGER.error("Failed to fetch latest release information")
        sys_exit(status)

    latest_version = latest_release["tag_name"].removeprefix("v")

    if is_newer_version_available(current_version, latest_version):
        # Version details
        latest_version_text = f"\033[1;92m{latest_version}\033[0m"
        current_version_text = f"\033[1;93m{current_version}\033[0m"
        release_notes_url = f"https://github.com/bunkerity/bunkerweb/releases/v{latest_version}"
        release_notes_url_text = f"\033[4;94m{release_notes_url}\033[0m"

        # Centering based on the longest line length
        alert_message = "🚨  A NEW VERSION OF BUNKERWEB IS AVAILABLE!  🚨"
        latest_version_line = f"Latest Version: {latest_version_text}"
        current_version_line = f"Current Version: {current_version_text}"
        release_notes_url_line = f"Release Notes: {release_notes_url_text}"

        # Determine the longest line length
        longest_line_length = max(
            len(alert_message),
            len(latest_version_line),
            len(current_version_line),
            len(release_notes_url_line),
        )

        # Centering the lines within the box width
        alert_message_padded = alert_message.center(longest_line_length - 13)
        latest_version_padded = latest_version_line.center(longest_line_length)
        current_version_padded = current_version_line.center(longest_line_length)
        LOGGER.warning(
            (
                f"\n\033[1;91m+{'—' * (longest_line_length - 7)}+\033[0m\n"
                f"\033[1;91m|{' ' * (longest_line_length - 7)}|\033[0m\n"
                f"\033[1;91m|  \033[1;97m{alert_message_padded}\033[1;91m  |\033[0m\n"
                f"\033[1;91m|{' ' * (longest_line_length - 7)}|\033[0m\n"
                f"\033[1;91m|  \033[1;97m{latest_version_padded}\033[1;91m  |\033[0m\n"
                f"\033[1;91m|  \033[1;97m{current_version_padded}\033[1;91m  |\033[0m\n"
                f"\033[1;91m|{' ' * (longest_line_length - 7)}|\033[0m\n"
                f"\033[1;91m|  \033[1;97m{release_notes_url_line}\033[1;91m  |\033[0m\n"
                f"\033[1;91m|{' ' * (longest_line_length - 7)}|\033[0m\n"
                f"\033[1;91m+{'—' * (longest_line_length - 7)}+\033[0m"
            )
        )
    else:
        LOGGER.info(f"No newer eligible version available (current: {current_version}, latest eligible: {latest_version})")
except SystemExit:
    # sys_exit inside the try block must exit with its own code, not be relabeled a crash.
    raise
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running update-check.py :\n{e}")

sys_exit(status)
