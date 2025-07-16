#!/usr/bin/env python3

from os import sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from time import sleep

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="joba-update-check",
    log_file_path="/var/log/bunkerweb/jobs.log"
)

logger.debug("Debug mode enabled for jobs-update-check")

from requests import get
from requests.exceptions import ConnectionError

from common_utils import get_version  # type: ignore

status = 0

try:
    logger.debug("Starting BunkerWeb update check process")

    # Get latest stable release from GitHub API with retry mechanism.
    def get_latest_stable_release():
        logger.debug("get_latest_stable_release() called")
        max_retries = 3
        retry_count = 0
        logger.debug("Starting GitHub API request for latest releases")
        
        while retry_count < max_retries:
            try:
                logger.debug(f"GitHub API request attempt {retry_count + 1}/{max_retries}")
                response = get("https://api.github.com/repos/bunkerity/bunkerweb/releases", 
                             headers={"User-Agent": "BunkerWeb"}, timeout=3)
                logger.debug(f"GitHub API response: status={response.status_code}")
                break
            except ConnectionError as e:
                retry_count += 1
                logger.debug(f"Connection error on attempt {retry_count}: {e}")
                if retry_count == max_retries:
                    raise e
                logger.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)
                
        response.raise_for_status()
        releases = response.json()
        logger.debug(f"Received {len(releases)} releases from GitHub API")

        # Find first non-prerelease version
        for i, release in enumerate(releases):
            logger.debug(f"Checking release {i+1}: {release.get('tag_name', 'unknown')} (prerelease: {release.get('prerelease', False)})")
            if not release["prerelease"]:
                logger.debug(f"Found latest stable release: {release['tag_name']}")
                return release
                
        logger.warning("No stable releases found in GitHub API response")
        return None

    logger.debug("Fetching latest release information")
    latest_release = get_latest_stable_release()

    if not latest_release:
        status = 1
        logger.error("Failed to fetch latest release information")
        sys_exit(status)

    logger.debug("Getting current BunkerWeb version")
    current_version = get_version()
    latest_version = latest_release["tag_name"].removeprefix("v")
    
    logger.debug(f"Version comparison: current={current_version}, latest={latest_version}")
    logger.debug(f"Release info: name={latest_release.get('name', 'N/A')}, published={latest_release.get('published_at', 'N/A')}")

    if current_version != latest_version:
        logger.debug("New version available, preparing update notification")
        
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
        
        logger.debug(f"Alert box dimensions: longest line={longest_line_length} characters")

        # Centering the lines within the box width
        alert_message_padded = alert_message.center(longest_line_length - 13)
        latest_version_padded = latest_version_line.center(longest_line_length)
        current_version_padded = current_version_line.center(longest_line_length)
        
        logger.debug("Displaying formatted update notification")
        logger.warning(
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
        
        logger.debug("Update notification displayed successfully")
    else:
        logger.info(f"Latest version is already installed: {current_version}")
        logger.debug("No update needed, current version is latest")
        
    logger.debug("Update check process completed successfully")
    
except BaseException as e:
    status = 2
    logger.exception("Exception while running update-check.py")

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
