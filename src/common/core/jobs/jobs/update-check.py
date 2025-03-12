#!/usr/bin/env python3

from os import sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from time import sleep

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from requests.exceptions import ConnectionError

from common_utils import get_version  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("UPDATE-CHECK")
status = 0

try:

    def get_latest_stable_release():
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = get("https://api.github.com/repos/bunkerity/bunkerweb/releases", headers={"User-Agent": "BunkerWeb"}, timeout=3)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)
        response.raise_for_status()
        releases = response.json()

        for release in releases:
            if not release["prerelease"]:
                return release
        return None

    latest_release = get_latest_stable_release()

    if not latest_release:
        status = 1
        LOGGER.error("Failed to fetch latest release information")
        sys_exit(status)

    current_version = get_version()
    latest_version = latest_release["tag_name"].removeprefix("v")

    if current_version != latest_version:
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
        LOGGER.info(f"Latest version is already installed: {current_version}")
except BaseException as e:
    status = 2
    LOGGER.error(f"Exception while running update-check.py :\n{e}")

sys_exit(status)
