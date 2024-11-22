#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, compile as re_compile
from subprocess import CalledProcessError, run
from sys import exit as sys_exit, path as sys_path
from typing import Dict, Set
from uuid import uuid4
from json import dumps
from shutil import copy, copytree, move, rmtree
from tarfile import open as tar_open
from zipfile import ZipFile

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
from requests import get

from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

PLUGIN_NAME_RX = re_compile(r"^# Plugin name: (?P<name>.+)$", MULTILINE)
PLUGIN_VERSION_RX = re_compile(r"^# Plugin version: (?P<version>.+)$", MULTILINE)

CRS_PLUGINS_DIR = Path(sep, "var", "cache", "bunkerweb", "modsecurity", "crs", "plugins")
NEW_PLUGINS_DIR = Path(sep, "var", "tmp", "bunkerweb", "crs-new-plugins")
TMP_DIR = Path(sep, "var", "tmp", "bunkerweb", "crs-plugins")
PATCH_SCRIPT = Path(sep, "usr", "share", "bunkerweb", "core", "modsecurity", "misc", "patch.sh")
LOGGER = setup_logger("modsecurity.download-crs-plugins", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    if not PATCH_SCRIPT.is_file():
        LOGGER.error(f"Patch script not found: {PATCH_SCRIPT}")
        sys_exit(1)

    # * Check if we're using the 4 or nightly version of the Core Rule Set (CRS)
    use_right_crs_version = False
    use_modsecurity_crs_plugins = False

    services = getenv("SERVER_NAME", "").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split(" ")
    services_plugin_urls = {}

    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_MODSECURITY_CRS_VERSION", getenv("MODSECURITY_CRS_VERSION", "4")) != "3":
                use_right_crs_version = True

            if getenv(f"{first_server}_USE_MODSECURITY_CRS_PLUGINS", getenv("USE_MODSECURITY_CRS_PLUGINS", "no")) == "yes":
                use_modsecurity_crs_plugins = True

            service_plugin_urls = getenv(f"{first_server}_MODSECURITY_CRS_PLUGIN_URLS", getenv("MODSECURITY_CRS_PLUGIN_URLS", "")).strip()
            if service_plugin_urls:
                services_plugin_urls[first_server] = set(service_plugin_urls.split(" "))
    else:
        if getenv("MODSECURITY_CRS_VERSION", "4") != "3":
            use_right_crs_version = True

        if getenv("USE_MODSECURITY_CRS_PLUGINS", "no") == "yes":
            use_modsecurity_crs_plugins = True

        plugin_urls = getenv("MODSECURITY_CRS_PLUGIN_URLS", "").strip()
        if plugin_urls:
            services_plugin_urls[services[0]] = set(plugin_urls.split(" "))

    if not use_modsecurity_crs_plugins:
        LOGGER.info("Core Rule Set (CRS) plugins are disabled, skipping download...")
        sys_exit(0)
    elif not services_plugin_urls:
        LOGGER.info("No Core Rule Set (CRS) plugins URLs found, skipping download...")
        sys_exit(0)
    elif not use_right_crs_version:
        LOGGER.warning("No service is using a compatible Core Rule Set (CRS) version with the plugins (4 or nightly), skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER)

    downloaded_plugins: Dict[str, Set[str]] = {}
    service_plugins: Dict[str, Set[str]] = {service: set() for service in services}
    changes = False

    # Loop on plugin URLs
    LOGGER.info("Checking if any Core Rule Set (CRS) plugin needs to be updated...")
    for service, plugin_urls in services_plugin_urls.items():
        installed_plugins = set()

        for crs_plugin_url in plugin_urls:
            if crs_plugin_url in downloaded_plugins:
                LOGGER.debug(f"CRS plugin {crs_plugin_url} has already been downloaded, skipping...")
                installed_plugins.update(downloaded_plugins[crs_plugin_url])
                continue

            downloaded_plugins[crs_plugin_url] = set()

            with BytesIO() as content:
                try:
                    resp = get(crs_plugin_url, headers={"User-Agent": "BunkerWeb"}, stream=True, timeout=5)

                    if resp.status_code != 200:
                        LOGGER.warning(f"Got status code {resp.status_code}, skipping download of plugin(s) with URL {crs_plugin_url}...")
                        continue

                    # Iterate over the response content in chunks
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            content.write(chunk)

                    content.seek(0)
                except BaseException as e:
                    LOGGER.error(f"Exception while downloading plugin(s) with URL {crs_plugin_url} :\n{e}")
                    continue

                # Extract it to tmp folder
                temp_dir = TMP_DIR.joinpath(str(uuid4()))
                try:
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    file_type = Magic(mime=True).from_buffer(content.getvalue())
                    content.seek(0)

                    if file_type == "application/zip":
                        with ZipFile(content) as zf:
                            zf.extractall(path=temp_dir)
                    elif file_type == "application/gzip":
                        with tar_open(fileobj=content, mode="r:gz") as tar:
                            try:
                                tar.extractall(path=temp_dir, filter="data")
                            except TypeError:
                                tar.extractall(path=temp_dir)
                    elif file_type == "application/x-tar":
                        with tar_open(fileobj=content, mode="r") as tar:
                            try:
                                tar.extractall(path=temp_dir, filter="data")
                            except TypeError:
                                tar.extractall(path=temp_dir)
                    else:
                        LOGGER.error(f"Unknown file type for {crs_plugin_url}, either zip or tar are supported, skipping...")
                        continue
                except BaseException as e:
                    LOGGER.error(f"Exception while decompressing plugin(s) from {crs_plugin_url} :\n{e}")
                    continue

            plugin_name = ""
            plugin_id = ""

            # Check if the plugins are valid, if they are already installed and if they need to be updated
            for plugin_config in temp_dir.rglob("**/*-config.conf"):
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
                    LOGGER.error(f"Exception while checking plugin {plugin_config} :\n{e}")
                    status = 2
                    continue

            # * Patch the rules so we can extract the rule IDs when matching
            try:
                LOGGER.info(f"Patching Core Rule Set (CRS) plugin {plugin_name}...")
                result = run([PATCH_SCRIPT.as_posix(), NEW_PLUGINS_DIR.joinpath(plugin_id).as_posix()], check=True)
            except CalledProcessError as e:
                LOGGER.error(f"Failed to patch Core Rule Set (CRS) plugin {plugin_name}: {e}")
                sys_exit(1)

            LOGGER.info(f"Successfully patched Core Rule Set (CRS) plugin {plugin_name}.")

            downloaded_plugins[crs_plugin_url] = installed_plugins.copy()

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
    LOGGER.error(f"Exception while running download-crs-plugins.py :\n{e}")

rmtree(TMP_DIR, ignore_errors=True)
rmtree(NEW_PLUGINS_DIR, ignore_errors=True)

sys_exit(status)
