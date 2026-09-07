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
from typing import Dict, Optional, Set, Tuple
from uuid import uuid4
from json import dumps, loads
from shutil import copy, copytree, rmtree
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
from requests.exceptions import ConnectionError, Timeout

from common_utils import bytes_hash, safe_tar_extractall, safe_zip_extractall  # type: ignore
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

# Exponential backoff schedule for a retryable failure (timeout, connection error, 5xx, or a
# GitHub rate limit). A response's own Retry-After header wins over this schedule when present --
# GitHub tells us exactly when it will accept the next call.
RETRY_BACKOFFS_SECONDS = (2, 4, 8)


def _is_rate_limited(response) -> bool:
    """A plain 429, or a GitHub secondary-rate-limit 403 (its rate-limit 403s carry this header;
    an auth/permission 403 does not)."""
    if response.status_code == 429:
        return True
    return response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"


def _retry_after_seconds(response) -> Optional[int]:
    """Clamped to the longest of our own backoffs: GitHub's primary rate limit sends a
    ``Retry-After`` in MINUTES, and honouring it uncapped can sleep past
    ``src/worker/app.py``'s ``task_soft_time_limit`` -- a killed task loses its delivery
    (``src/worker/tasks.py``), which the flat pre-fix 3s sleep could never do. A capped wait that
    is too short just means one more retry loop; an uncapped one that is too long can lose the job.
    """
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0, min(int(float(value)), max(RETRY_BACKOFFS_SECONDS)))
    except (TypeError, ValueError):
        return None


def request_with_retry(request_fn, *args, max_retries: int = 4, **kwargs):
    """Call ``request_fn(*args, **kwargs)`` (a ``requests.get``/``requests.head`` bound call),
    retrying up to ``max_retries`` total attempts (the first try plus up to
    ``len(RETRY_BACKOFFS_SECONDS)`` retries -- default 4: one attempt, then up to three retries so
    all of 2s/4s/8s are reachable) on a connection failure, a read timeout, a 5xx, or a GitHub
    rate limit -- honouring the response's ``Retry-After`` header when present, falling back to
    ``RETRY_BACKOFFS_SECONDS`` otherwise.

    Returns the last response once retries are exhausted -- a 5xx/429/403 caller already knows
    how to turn that into a failure via ``raise_for_status``/its own status-code check -- or
    re-raises the last connection/timeout error, so every existing caller's error handling is
    unchanged.
    """
    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries):
        try:
            response = request_fn(*args, **kwargs)
        except (ConnectionError, Timeout) as e:
            last_exc = e
            if attempt == max_retries - 1:
                raise
            delay = RETRY_BACKOFFS_SECONDS[min(attempt, len(RETRY_BACKOFFS_SECONDS) - 1)]
            LOGGER.warning(f"{type(e).__name__}, retrying in {delay}s... ({attempt + 1}/{max_retries})")
            sleep(delay)
            continue

        if (response.status_code >= 500 or _is_rate_limited(response)) and attempt < max_retries - 1:
            delay = _retry_after_seconds(response) or RETRY_BACKOFFS_SECONDS[min(attempt, len(RETRY_BACKOFFS_SECONDS) - 1)]
            LOGGER.warning(f"Got status code {response.status_code}, retrying in {delay}s... ({attempt + 1}/{max_retries})")
            # Every current caller passes stream=True, so the connection is not returned to the
            # pool until the body is read or the response is closed -- an unclosed retried 5xx
            # would pin a pooled connection per retry, which the old ConnectionError-only loop
            # could never do (there was no response object to leak on that path).
            response.close()
            sleep(delay)
            continue

        return response

    raise last_exc or RuntimeError("request_with_retry: max_retries <= 0")  # pragma: no cover -- defensive, unreachable at max_retries=4


# Set by any plugin this run could not resolve, download or unpack. The final swap is destructive
# (`rmtree(CRS_PLUGINS_DIR)`) and the rendered configuration is the INTERSECTION of
# `crs-plugins.json` and what sits in that directory, so swapping after a PARTIAL run silently
# drops the failed plugin's rules from the WAF. A stale rule set for one run beats a missing one.
#
# Emptiness is deliberately NOT the signal (that is `should_keep_previous_cache`'s job, and it only
# ever fires when NOTHING resolved): a run can resolve every URL and still download none of them,
# and conversely a plugin the operator removed or mistyped is a registry miss, not a failure, and
# must be allowed to disappear.
plugin_failures = False


def should_keep_previous_cache(service_plugins: Dict[str, Set[str]], crs_plugins_dir: Path, plugin_failures: bool = False) -> bool:
    """True when this run must NOT publish its plugin set, for either of two reasons.

    ``plugin_failures`` -- at least one plugin could not be resolved, downloaded or unpacked. The
    swap is destructive and the render is the intersection of ``crs-plugins.json`` and
    CRS_PLUGINS_DIR, so publishing a partial set silently drops the failed plugin's rules from the
    WAF. Unconditional, deliberately: on a first run there is nothing to keep, but publishing an
    incomplete set as if it were complete is still the worse outcome, and the caller reports a
    failure so the next run retries from scratch.

    Or ``service_plugins`` ended up with NOTHING for ANY service while a previous run's plugin set
    is still on disk -- so this run cannot replace a working, previously-cached plugin set with an
    empty one.

    Covers the brief's own CI-red scenario: a registry/version LOOKUP failing for every
    configured plugin, so `service_plugins` never gets touched at all and stays every-value-empty
    from its `{service: set() for service in services}` initialisation. It does NOT cover every
    plugin's ARCHIVE download then failing after a successful lookup: `service_plugins[service] =
    plugins` (pre-existing, in the registry-resolution branch, well above the "Loop on plugins"
    section this function's caller runs after) aliases the RESOLVED URL SET into this same dict
    the moment a lookup succeeds -- so `any(service_plugins.values())` is already True from that
    alone, before a single byte is downloaded. A lookup-success-then-every-download-fails run
    therefore still wipes CRS_PLUGINS_DIR. Out of scope for this bugfix (the brief's failure mode
    is the lookup, not the download) when this docstring was written -- ``plugin_failures``, ported
    from dev ``a92cc3187``, is what covers it now.
    """
    if plugin_failures:
        return True

    any_installed_this_run = any(service_plugins.values())
    had_existing_plugins = crs_plugins_dir.is_dir() and any(crs_plugins_dir.iterdir())
    return not any_installed_this_run and had_existing_plugins


def swap_and_cache_plugins(service_plugins: Dict[str, Set[str]], plugin_failures: bool = False) -> bool:
    """Publish this run's downloaded plugin set (or keep the previous one, see
    ``should_keep_previous_cache``) and push it to the job cache. Returns ``render_changed``.

    A top-level function, not inlined in the script body: ``tests/unit/jobs/test_render_time_reflag.py``
    lifts the ``plugins_json = dumps(`` .. ``if not cached:`` span verbatim from this file's own
    source and dedents it by exactly one level, so that span must stay at a single indentation
    level -- it cannot live inside an ``if``/``else`` in the script body.
    """
    global status

    if should_keep_previous_cache(service_plugins, CRS_PLUGINS_DIR, plugin_failures):
        # Some or every plugin failed to resolve, download or unpack this run (see the retry/skip
        # handling above) -- wiping CRS_PLUGINS_DIR now would replace a working, previously-cached
        # plugin set with a partial one (or with nothing), which is worse than leaving it stale for
        # one run. Keep it as-is and report a failure; the next run retries from scratch.
        if plugin_failures:
            LOGGER.error("At least one Core Rule Set (CRS) plugin could not be installed, keeping the previously cached plugin set...")
        else:
            LOGGER.error("No Core Rule Set (CRS) plugin could be resolved or downloaded this run, keeping the previously cached plugin set...")
        status = 2
        return False

    rmtree(CRS_PLUGINS_DIR, ignore_errors=True)
    if NEW_PLUGINS_DIR.is_dir():
        copytree(NEW_PLUGINS_DIR, CRS_PLUGINS_DIR)
    else:
        CRS_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    # sorted(), not list(): the template emits one include per entry in the order this mapping gives,
    # so an unordered set would reshuffle the CRS plugin includes on every run and make the change
    # test below fire every day for nothing.
    plugins_json = dumps({service: sorted(plugins) for service, plugins in service_plugins.items()}, indent=2).encode()

    # This mapping is the render input: an already-installed plugin id keeps its extracted directory
    # untouched (the `copytree()` below), so the plugin files can only change when an id does, and an id
    # carries its version. Read the previous fingerprint BEFORE cache_file overwrites it.
    render_changed = bytes_hash(plugins_json) != JOB.cache_hash("crs-plugins.json")

    cached, err = JOB.cache_file("crs-plugins.json", plugins_json)
    if not cached:
        LOGGER.error(f"Failed to cache crs-plugins.json :\n{err}")
        status = 2

    cached, err = JOB.cache_dir(CRS_PLUGINS_DIR)
    if not cached:
        LOGGER.error(f"Error while saving Core Rule Set (CRS) plugins data to db cache: {err}")
        status = 2
    else:
        LOGGER.info("Successfully saved Core Rule Set (CRS) plugins data to db cache.")

    return render_changed


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
        response = request_with_retry(get, release_api_url, timeout=8)
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
                branch_check = request_with_retry(head, branch_url, timeout=8)
                if branch_check.status_code < 400:
                    return True, branch_url

            return False, "No branches found"
    except Exception as e:
        raise RuntimeError(f"Failed to deduce the download URL: {e}")


try:
    if not PATCH_SCRIPT.is_file():
        LOGGER.error(f"Patch script not found: {PATCH_SCRIPT}")
        # 2, not 1: in the job contract 1 means "changed, ship the cache and reload the fleet"
        # (src/worker/tasks.py:426), and `success = ret in (0, 1)` (:398) would also record this
        # failure as a success. A failure must do neither.
        sys_exit(2)

    # * Check if we're using a version of the Core Rule Set (CRS) compatible with plugins
    use_right_crs_version = False
    use_modsecurity_crs_plugins = False

    services = getenv("SERVER_NAME", "www.example.com").strip()

    if not services:
        LOGGER.warning("No services found, exiting...")
        sys_exit(0)

    services = services.split()
    services_plugins = {}

    if getenv("MULTISITE", "no") == "yes":
        for first_server in services:
            if getenv(f"{first_server}_MODSECURITY_CRS_VERSION", "4") != "3":
                use_right_crs_version = True

            if getenv(f"{first_server}_USE_MODSECURITY_CRS_PLUGINS", "yes") == "yes":
                use_modsecurity_crs_plugins = True

            service_plugins = getenv(f"{first_server}_MODSECURITY_CRS_PLUGINS", "").strip()
            if service_plugins:
                services_plugins[first_server] = set(service_plugins.split())
    else:
        if getenv("MODSECURITY_CRS_VERSION", "4") != "3":
            use_right_crs_version = True

        if getenv("USE_MODSECURITY_CRS_PLUGINS", "yes") == "yes":
            use_modsecurity_crs_plugins = True

        plugins = getenv("MODSECURITY_CRS_PLUGINS", "").strip()
        if plugins:
            services_plugins[services[0]] = set(plugins.split())

    if not use_modsecurity_crs_plugins:
        LOGGER.info("Core Rule Set (CRS) plugins are disabled, skipping download...")
        sys_exit(0)
    elif not services_plugins:
        LOGGER.info("No Core Rule Set (CRS) plugins found, skipping download...")
        sys_exit(0)
    elif not use_right_crs_version:
        LOGGER.warning("No service is using a compatible Core Rule Set (CRS) version with the plugins (4), skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    # Discard any staging tree left by an interrupted run, exactly as the end of this job does
    # (the two rmtree calls at the bottom). Both cleanups only run on a clean exit, so a killed
    # run leaves half-copied plugin directories behind -- and the check further down treats the
    # mere *existence* of NEW_PLUGINS_DIR/<plugin_id> as "already extracted, skip", so that
    # partial directory would be adopted as complete, copied over the live CRS_PLUGINS_DIR and
    # cached in the database. Services would then include a plugin's -config.conf with none of
    # its rule files behind it.
    #
    # Safe to purge: every run re-downloads and re-extracts each plugin URL before this loop, so
    # anything discarded here is rebuilt from the fresh download -- including a plugin that a
    # previous run had MOVED out of CRS_PLUGINS_DIR into staging.
    rmtree(NEW_PLUGINS_DIR, ignore_errors=True)

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
                    resp = request_with_retry(
                        get,
                        "https://raw.githubusercontent.com/coreruleset/plugin-registry/refs/heads/main/README.md",
                        headers={"User-Agent": "BunkerWeb"},
                        stream=True,
                        timeout=8,
                    )
                    if resp.status_code != 200:
                        LOGGER.error(f"Got status code {resp.status_code}, raising an exception...")
                        sys_exit(2)

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
                    sys_exit(2)

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
                    try:
                        success, url = get_download_url(plugin_data["repository"], plugin_version)
                    except RuntimeError as e:
                        # Retries in get_download_url/request_with_retry are exhausted -- a real
                        # infra failure, not a registry data problem. Skip this ONE plugin rather
                        # than letting it (an uncaught exception used to) crash the whole job and
                        # discard every other service/plugin's work.
                        #
                        # `plugin_failures` is why `status = 2` is safe here now (it was not before
                        # the port of dev a92cc3187, and this comment used to argue against it):
                        # the flag makes the final swap keep the PREVIOUS plugin set untouched, so
                        # a failure status describes what is on disk instead of contradicting it.
                        # Without it, status = 2 shipped the other plugins to disk and the DB cache
                        # but never referenced them in the rendered conf, and never retried, since
                        # the next run's fingerprint then matched.
                        LOGGER.error(f"Failed to get the download URL for plugin {plugin_name} (version: {plugin_version}) after retries: {e}")
                        plugin_failures = True
                        status = 2
                        continue
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
                try:
                    success, url = get_download_url(plugin_data["repository"])
                except RuntimeError as e:
                    # See the comment on the version-pinned branch above; same reasoning here.
                    LOGGER.error(f"Failed to get the download URL for plugin {plugin_name} after retries: {e}")
                    plugin_failures = True
                    status = 2
                    continue
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
                    resp = request_with_retry(get, crs_plugin, headers={"User-Agent": "BunkerWeb"}, stream=True, timeout=8)
                    if resp.status_code != 200:
                        LOGGER.warning(f"Got status code {resp.status_code}, skipping download of plugin(s) with URL {crs_plugin}...")
                        plugin_failures = True
                        status = 2
                        continue

                    # Write content to BytesIO
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            content.write(chunk)

                    content.seek(0)
                except BaseException as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while downloading plugin(s) with URL {crs_plugin} :\n{e}")
                    plugin_failures = True
                    status = 2
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
                                safe_zip_extractall(zf, temp_dir)
                            LOGGER.info(f"Successfully extracted ZIP file to {temp_dir}")
                        except BadZipFile as e:
                            LOGGER.debug(format_exc())
                            LOGGER.error(f"Invalid ZIP file: {e}")
                            plugin_failures = True
                            status = 2
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
                                safe_tar_extractall(tar, temp_dir)
                            LOGGER.info(f"Successfully extracted TAR file to {temp_dir}")
                        except TarError as e:
                            LOGGER.debug(format_exc())
                            LOGGER.error(f"Invalid TAR file: {e}")
                            plugin_failures = True
                            status = 2
                            continue

                    else:
                        LOGGER.error(f"Unknown file type for {crs_plugin}, either ZIP or TAR is supported, skipping...")
                        plugin_failures = True
                        status = 2
                        continue

                except BaseException as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Exception while decompressing plugin(s) from {crs_plugin}:\n{e}")
                    plugin_failures = True
                    status = 2
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
                        # copytree, not move: CRS_PLUGINS_DIR has to stay COMPLETE until the swap,
                        # or the `plugin_failures` guard keeps a set this loop has already
                        # half-emptied -- "keep the previous plugin set" would then still lose every
                        # plugin that was reused before the failure.
                        copytree(CRS_PLUGINS_DIR.joinpath(plugin_id), NEW_PLUGINS_DIR.joinpath(plugin_id))
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
                sys_exit(2)

            LOGGER.info(f"Successfully patched Core Rule Set (CRS) plugin {plugin_name}.")

            downloaded_plugins[crs_plugin] = installed_plugins.copy()

        service_plugins[service].update(installed_plugins)

    render_changed = swap_and_cache_plugins(service_plugins, plugin_failures)

    if status == 0:
        status = 1

    # A new plugin set needs a RE-RENDER, not just a push. The include lines are baked in at render
    # time: confs/server-http/modsecurity-rules.conf.modsec:136-158 and :212-226 walk crs-plugins.json
    # and emit one `include` per -config/-before/-after file. Exiting 1 buys this job a cache push and
    # a reload (worker/tasks.py:426), and neither can apply its own output: reloading re-reads the
    # *rendered* conf, which has no include for a plugin that did not exist when it was rendered.
    # Flagging the plugin makes the scheduler dispatch push-configs (main.py:1131 -> :944), which
    # re-renders first. Cold start is the same case: the conf is rendered before this job has ever
    # run, so without the flag the downloaded plugins stay unreferenced until some unrelated change.
    if render_changed and status == 1:
        err = JOB.db.checked_changes(["config"], plugins_changes=["modsecurity"], value=True)
        if err:
            LOGGER.error(f"Couldn't flag modsecurity for regeneration, the CRS plugins will not be included : {err}")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running download-crs-plugins.py :\n{e}")

rmtree(TMP_DIR, ignore_errors=True)
rmtree(NEW_PLUGINS_DIR, ignore_errors=True)

sys_exit(status)
