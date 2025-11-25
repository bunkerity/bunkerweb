#!/usr/bin/env python3

from datetime import datetime, timedelta
from io import BytesIO
from mimetypes import guess_type
from os import getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, compile as re_compile
from subprocess import CalledProcessError, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Dict, Set, Tuple
from uuid import uuid4
from json import dumps, loads
from shutil import copy, copytree, move, rmtree
from tarfile import TarError, open as tar_open
from zipfile import BadZipFile, ZipFile

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("api",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from magic import Magic
from requests import get, head
from requests.exceptions import ConnectionError

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

PLUGIN_NAME_RX = re_compile(r"^# Plugin name: (?P<name>.+)$", MULTILINE)
PLUGIN_VERSION_RX = re_compile(r"^# Plugin version: (?P<version>.+)$", MULTILINE)

CRS_PLUGINS_DIR = Path(sep, "var", "cache", "bunkerweb", "modsecurity", "crs", "plugins")
NEW_PLUGINS_DIR = Path(sep, "var", "tmp", "bunkerweb", "crs-new-plugins")
TMP_DIR = Path(sep, "var", "tmp", "bunkerweb", "crs-plugins")
PATCH_SCRIPT = Path(sep, "usr", "share", "bunkerweb", "core", "modsecurity", "misc", "patch.sh")
LOGGER = getLogger("MODSECURITY.DOWNLOAD.CRS_PLUGINS")
status = 0


def get_download_url(repo_url, version=None) -> Tuple[bool, str]:
    """
    Get the URL of the downloadable file for the specified version or deduce the latest available version.
    If the `main` branch doesn't exist, fall back to the `master` branch.

    Args:
        repo_url (str): The GitHub repository URL (e.g., https://github.com/owner/repo).
        version (str, optional): The version tag. If not provided, deduces the latest release or falls back to the default branch.

    Returns:
        str: The deduced download URL.
    """
    try:
        if version:
            # If a specific version is provided, construct the URL for the downloadable file
            return True, f"{repo_url}/archive/refs/tags/{version}.zip"

        # Try fetching the latest release
        release_api_url = f"{repo_url.replace('github.com', 'api.github.com/repos', 1)}/releases"
        LOGGER.debug(f"Checking {release_api_url}...")
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = get(release_api_url, timeout=8)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)
        response.raise_for_status()
        releases = response.json()
        latest_release = None

        for release in releases:
            if not release["prerelease"]:
                latest_release = release["tag_name"]
                break

        if latest_release:
            return True, f"{repo_url}/archive/refs/tags/{latest_release}.tar.gz"
        else:
            # Fall back to checking branches (main -> master)
            for branch in ("main", "master"):
                branch_url = f"{repo_url}/archive/refs/heads/{branch}.zip"
                LOGGER.debug(f"Checking {branch_url}...")
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        branch_check = head(branch_url, timeout=8)
                        break
                    except ConnectionError as e:
                        retry_count += 1
                        if retry_count == max_retries:
                            raise e
                        LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                        sleep(3)
                if branch_check.status_code < 400:
                    return True, branch_url

            return False, "No branches found"
    except Exception as e:
        raise RuntimeError(f"Failed to deduce the download URL: {e}")


try:
    if not PATCH_SCRIPT.is_file():
        LOGGER.error(f"Patch script not found: {PATCH_SCRIPT}")
        sys_exit(1)

    # * Check if we're using the 4 or nightly version of the Core Rule Set (CRS)
    use_right_crs_version = False
    use_modsecurity_crs_plugins = False

    services = getenv("SERVER_NAME", "www.example.com").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_plugins = {}

    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_MODSECURITY_CRS_VERSION", "4") != "3":
                use_right_crs_version = True

            if getenv(f"{first_server}_USE_MODSECURITY_CRS_PLUGINS", "yes") == "yes":
                use_modsecurity_crs_plugins = True

            service_plugins = getenv(f"{first_server}_MODSECURITY_CRS_PLUGINS", "").strip()
            if service_plugins:
                services_plugins[first_server] = set(service_plugins.split(" "))
    else:
        if getenv("MODSECURITY_CRS_VERSION", "4") != "3":
            use_right_crs_version = True

        if getenv("USE_MODSECURITY_CRS_PLUGINS", "yes") == "yes":
            use_modsecurity_crs_plugins = True

        plugins = getenv("MODSECURITY_CRS_PLUGINS", "").strip()
        if plugins:
            services_plugins[services[0]] = set(plugins.split(" "))

    if not use_modsecurity_crs_plugins:
        LOGGER.info("Core Rule Set (CRS) plugins are disabled, skipping download...")
        sys_exit(0)
    elif not services_plugins:
        LOGGER.info("No Core Rule Set (CRS) plugins found, skipping download...")
        sys_exit(0)
    elif not use_right_crs_version:
        LOGGER.warning("No service is using a compatible Core Rule Set (CRS) version with the plugins (4 or nightly), skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    downloaded_plugins: Dict[str, Set[str]] = {}
    service_plugins: Dict[str, Set[str]] = {service: set() for service in services}

    # If there is at least one plugin that isn't an url, we need to check the registry
    if any(not plugin.startswith("http") for plugins in services_plugins.values() for plugin in plugins):
        LOGGER.info("One of the Core Rule Set (CRS) plugins is not an URL, checking the registry...")

        plugin_registry = JOB.get_cache("plugin_registry.json", with_info=True, with_data=True)

        if isinstance(plugin_registry, dict):
            up_to_date = plugin_registry.get("last_update") and plugin_registry["last_update"] > (datetime.now().astimezone() - timedelta(hours=1)).timestamp()

            if up_to_date:
                try:
                    plugin_registry = loads(plugin_registry.get("data"))
                except BaseException as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Failed to load the plugin registry data from cache: \n{e}")
                    plugin_registry = None
            else:
                LOGGER.info("The plugin registry has not been updated in the last hour, fetching the latest version...")
                plugin_registry = None

        if not isinstance(plugin_registry, dict):
            LOGGER.info("Fetching the plugin registry from the GitHub repository...")
            with BytesIO() as content:
                try:
                    # Download the file
                    max_retries = 3
                    retry_count = 0
                    while retry_count < max_retries:
                        try:
                            resp = get(
                                "https://raw.githubusercontent.com/coreruleset/plugin-registry/refs/heads/main/README.md",
                                headers={"User-Agent": "BunkerWeb"},
                                stream=True,
                                timeout=8,
                            )
                            break
                        except ConnectionError as e:
                            retry_count += 1
                            if retry_count == max_retries:
                                raise e
                            LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                            sleep(3)
                    if resp.status_code != 200:
                        LOGGER.error(f"Got status code {resp.status_code}, raising an exception...")
                        sys_exit(1)

                    # Write content to BytesIO
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            content.write(chunk)

                    content.seek(0)
                except SystemExit as e:
                    sys_exit(e.code)
                except BaseException as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while downloading the registry:\n{e}")
                    sys_exit(1)

                # Extract table lines (lines starting with "|")
                table_lines = [line for line in content.read().decode().splitlines() if line.startswith("|")]

            # Split each row into columns and clean the content
            table = [row.strip("|").split("|") for row in table_lines]
            table = [[cell.strip() for cell in row] for row in table]

            # Extract headers and data
            headers = table[0]  # First row as headers
            data = table[2:]  # Skip header separator row

            # Convert the registry table into a dictionary
            plugin_registry = {}
            clean_headers = [header.replace("*", "").strip().lower() for header in headers[1:]]

            for row in data:
                plugin_name = row[0].lower()
                # Extract values from cells, removing parentheses
                values = [cell.split("]")[-1].replace("(", "").replace(")", "").replace("&#9989;&nbsp;", "").strip().lower() for cell in row[1:]]
                plugin_registry[plugin_name] = dict(zip(clean_headers, values))

            cached, err = JOB.cache_file("plugin_registry.json", dumps(plugin_registry, indent=2).encode())
            if not cached:
                LOGGER.error(f"Error while caching plugin registry data: {err}")

        # LOGGER.debug(f"Plugin registry:\n{plugin_registry}")

        download_url_cache = {}
        for service, plugins in services_plugins.items():
            for plugin in plugins.copy():
                if plugin.startswith(("http://", "https://")):
                    continue

                plugins.remove(plugin)
                plugin_split = plugin.split("/")
                plugin_version = None

                if len(plugin_split) > 1:
                    plugin_version = plugin_split[1]

                plugin_name = plugin_split[0].lower()

                if plugin_name not in plugin_registry:
                    LOGGER.error(f"Plugin {plugin_name} not found in the registry, ignoring...")
                    continue

                plugin_data = plugin_registry[plugin_name]

                if "repository" not in plugin_data:
                    LOGGER.error(f"Plugin {plugin_name} is missing a Repository URL in the registry, ignoring...")
                    continue
                elif "private" in plugin_data.get("status", ""):
                    LOGGER.error(f"Plugin {plugin_name} is private, ignoring...")
                    continue

                # Build cache key using plugin name and version (or 'latest' if not provided)
                cache_key = f"{plugin_name}:{plugin_version}" if plugin_version else f"{plugin_name}:latest"

                if cache_key in download_url_cache:
                    LOGGER.debug(f"Using cached URL for plugin {plugin_name} with key {cache_key}")
                    plugins.add(download_url_cache[cache_key])
                    continue

                if plugin_version:
                    LOGGER.info(f"Plugin {plugin} found in the registry, fetching version {plugin_version}...")
                    success, url = get_download_url(plugin_data["repository"], plugin_version)
                    if not success:
                        LOGGER.error(f"Failed to get the download URL for plugin {plugin_name} (version: {plugin_version}): {url}")
                        continue
                    if plugin_data.get("status", "") != "tested":
                        LOGGER.warning(
                            f'Plugin {plugin_name} is marked as "{plugin_data["status"]}", be cautious when using it as there is no guarantee it will work'
                        )
                    LOGGER.debug(f"Plugin {plugin_name} (version: {plugin_version}) corresponds to URL {url}")
                    plugins.add(url)
                    download_url_cache[cache_key] = url
                    continue

                LOGGER.info(f"Plugin {plugin} found in the registry, fetching latest version...")
                success, url = get_download_url(plugin_data["repository"])
                if not success:
                    LOGGER.error(f"Failed to get the download URL for plugin {plugin_name}: {url}")
                    continue
                if plugin_data.get("status", "") != "tested":
                    LOGGER.warning(
                        f'Plugin {plugin_name} is marked as "{plugin_data["status"]}", be cautious when using it as there is no guarantee it will work'
                    )

                LOGGER.debug(f"Plugin {plugin_name} corresponds to URL {url}")
                plugins.add(url)
                download_url_cache[cache_key] = url

                service_plugins[service] = plugins

        LOGGER.debug(f"Service plugins:\n{service_plugins}")

    # Loop on plugins
    LOGGER.info("Checking if any Core Rule Set (CRS) plugin needs to be updated...")
    for service, plugins in services_plugins.items():
        installed_plugins = set()

        for crs_plugin in plugins:
            if crs_plugin in downloaded_plugins:
                LOGGER.debug(f"CRS plugin {crs_plugin} has already been downloaded, skipping...")
                installed_plugins.update(downloaded_plugins[crs_plugin])
                continue

            downloaded_plugins[crs_plugin] = set()

            with BytesIO() as content:
                try:
                    # Download the file
                    max_retries = 3
                    retry_count = 0
                    while retry_count < max_retries:
                        try:
                            resp = get(crs_plugin, headers={"User-Agent": "BunkerWeb"}, stream=True, timeout=8)
                            break
                        except ConnectionError as e:
                            retry_count += 1
                            if retry_count == max_retries:
                                raise e
                            LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                            sleep(3)
                    if resp.status_code != 200:
                        LOGGER.warning(f"Got status code {resp.status_code}, skipping download of plugin(s) with URL {crs_plugin}...")
                        continue

                    # Write content to BytesIO
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            content.write(chunk)

                    content.seek(0)
                except BaseException as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while downloading plugin(s) with URL {crs_plugin} :\n{e}")
                    continue

                # Extract it to tmp folder
                temp_dir = TMP_DIR.joinpath(str(uuid4()))
                try:
                    temp_dir.mkdir(parents=True, exist_ok=True)

                    # Detect file type
                    file_type = Magic(mime=True).from_buffer(content.getvalue())
                    LOGGER.debug(f"Detected file type: {file_type}")

                    # Fallback to file extension detection
                    if file_type == "application/octet-stream":
                        file_type = guess_type(crs_plugin)[0] or "application/octet-stream"
                        LOGGER.debug(f"Guessed file type from URL: {file_type}")

                    content.seek(0)

                    # Handle ZIP files
                    if file_type == "application/zip" or crs_plugin.endswith(".zip"):
                        try:
                            with ZipFile(content) as zf:
                                zf.extractall(path=temp_dir)
                            LOGGER.info(f"Successfully extracted ZIP file to {temp_dir}")
                        except BadZipFile as e:
                            LOGGER.debug(format_exc())
                            LOGGER.error(f"Invalid ZIP file: {e}")
                            continue

                    # Handle TAR files (all compression types)
                    elif file_type.startswith("application/x-tar") or crs_plugin.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
                        try:
                            # Detect the appropriate tar mode
                            tar_mode = "r"
                            if crs_plugin.endswith(".gz") or file_type == "application/gzip":
                                tar_mode = "r:gz"
                            elif crs_plugin.endswith(".bz2"):
                                tar_mode = "r:bz2"
                            elif crs_plugin.endswith(".xz"):
                                tar_mode = "r:xz"

                            with tar_open(fileobj=content, mode=tar_mode) as tar:
                                tar.extractall(path=temp_dir)
                            LOGGER.info(f"Successfully extracted TAR file to {temp_dir}")
                        except TarError as e:
                            LOGGER.debug(format_exc())
                            LOGGER.error(f"Invalid TAR file: {e}")
                            continue

                    else:
                        LOGGER.error(f"Unknown file type for {crs_plugin}, either ZIP or TAR is supported, skipping...")
                        continue

                except BaseException as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while decompressing plugin(s) from {crs_plugin}:\n{e}")
                    continue

            plugin_name = ""
            plugin_id = ""

            # Check if the plugins are valid, if they are already installed and if they need to be updated
            for plugin_config in list(temp_dir.rglob("**/*-config.conf")):
                try:
                    if plugin_config.is_dir():
                        LOGGER.debug(f"CRS plugin {plugin_config} is a directory, skipping...")
                        continue
                    plugin_config_content = plugin_config.read_text()

                    # Check if the plugin has a name
                    plugin_name_match = PLUGIN_NAME_RX.search(plugin_config_content)
                    if not plugin_name_match:
                        LOGGER.warning(f"CRS plugin {plugin_config} is missing a name, using filename instead...")
                        plugin_name = plugin_config.stem.replace("-config", "")
                    else:
                        plugin_name = plugin_name_match.group("name")

                    # Check if the plugin has a version
                    plugin_version_match = PLUGIN_VERSION_RX.search(plugin_config_content)
                    if not plugin_version_match:
                        LOGGER.warning(f"CRS plugin {plugin_name} is missing a version, skipping...")
                        continue
                    plugin_version = plugin_version_match.group("version")

                    LOGGER.debug(f"Checking plugin {plugin_name} (version: {plugin_version})...")

                    plugin_id = f"{plugin_name}-{plugin_version}"

                    if NEW_PLUGINS_DIR.joinpath(plugin_id).is_dir():
                        LOGGER.debug(f"CRS plugin {plugin_name} (version: {plugin_version}) has already been extracted earlier, skipping...")
                        installed_plugins.add(plugin_id)
                        continue
                    elif CRS_PLUGINS_DIR.joinpath(plugin_id, plugin_config.name).is_file():
                        LOGGER.info(f"CRS plugin {plugin_name} (version: {plugin_version}) is already installed, we don't need to install it")
                        move(CRS_PLUGINS_DIR.joinpath(plugin_id), NEW_PLUGINS_DIR.joinpath(plugin_id))
                        installed_plugins.add(plugin_id)
                        continue

                    NEW_PLUGINS_DIR.joinpath(plugin_id).mkdir(parents=True, exist_ok=True)
                    for plugin_file in plugin_config.parent.glob("*"):
                        if plugin_file.is_dir():
                            copytree(plugin_file, NEW_PLUGINS_DIR.joinpath(plugin_id))
                            continue
                        copy(plugin_file, NEW_PLUGINS_DIR.joinpath(plugin_id))

                    LOGGER.info(f"CRS plugin {plugin_name} (version: {plugin_version}) has been installed")
                    installed_plugins.add(plugin_id)
                except BaseException as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while checking plugin {plugin_config} :\n{e}")
                    status = 2
                    continue

            # * Patch the rules so we can extract the rule IDs when matching
            try:
                LOGGER.info(f"Patching Core Rule Set (CRS) plugin {plugin_name}...")
                result = run(
                    [PATCH_SCRIPT.as_posix(), NEW_PLUGINS_DIR.joinpath(plugin_id).as_posix()],
                    check=True,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
            except CalledProcessError as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Failed to patch Core Rule Set (CRS) plugin {plugin_name}: {e}")
                sys_exit(1)

            LOGGER.info(f"Successfully patched Core Rule Set (CRS) plugin {plugin_name}.")

            downloaded_plugins[crs_plugin] = installed_plugins.copy()

        service_plugins[service].update(installed_plugins)

    rmtree(CRS_PLUGINS_DIR, ignore_errors=True)
    if NEW_PLUGINS_DIR.is_dir():
        copytree(NEW_PLUGINS_DIR, CRS_PLUGINS_DIR)
    else:
        CRS_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    cached, err = JOB.cache_file("crs-plugins.json", dumps({service: list(plugins) for service, plugins in service_plugins.items()}, indent=2).encode())
    if not cached:
        LOGGER.error(f"Failed to cache crs-plugins.json :\n{err}")
        status = 2

    cached, err = JOB.cache_dir(CRS_PLUGINS_DIR)
    if not cached:
        LOGGER.error(f"Error while saving Core Rule Set (CRS) plugins data to db cache: {err}")
        status = 2
    else:
        LOGGER.info("Successfully saved Core Rule Set (CRS) plugins data to db cache.")

    if status == 0:
        status = 1
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running download-crs-plugins.py :\n{e}")

rmtree(TMP_DIR, ignore_errors=True)
rmtree(NEW_PLUGINS_DIR, ignore_errors=True)

sys_exit(status)
