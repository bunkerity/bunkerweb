from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from logging import getLogger
from os import getenv, sep
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from sys import path as sys_path
from tarfile import open as tar_open
from traceback import format_exc
from typing import Optional

from common_utils import bytes_hash, create_plugin_tar_gz, safe_tar_extractall  # type: ignore
from manual_plugins import read_manual_plugin  # type: ignore

from app.api_client import ApiClient
from app.i18n import LocaleThreadPoolExecutor
from app.perf import record_api_call
from app.models.config import Config
from app.models.instance import InstancesUtils
from app.models.ui_data import UIData
from app.plugin_api import PluginApi, RetiredDB

# The UI holds no database connection since 1.7; `DB` only still exists because 1.6 plugins import
# it. It is a proxy, not None, so the first use raises a RuntimeError naming the plugin and
# PLUGIN_API instead of an AttributeError on NoneType from somewhere deeper in the plugin.
DB = RetiredDB()

DATA = UIData(Path(sep, "var", "tmp", "bunkerweb").joinpath("ui_data.json"))

API_CLIENT = ApiClient(
    base_url=getenv("API_URL", "http://bw-api:5000"),
    api_token=getenv("API_TOKEN", ""),
)

# Every UI page is assembled from API calls, and what makes one slow is almost always their
# number. Counting them costs an integer per call and is what `Server-Timing` reports.
API_CLIENT.observer = record_api_call

# The supported data surface for plugin blueprints, `ui/actions.py` and `ui/hooks.py`: a subset of
# API_CLIENT with the user/session/admin methods left out. See `app/plugin_api.py`.
PLUGIN_API = PluginApi(API_CLIENT)

BW_CONFIG = Config(data=DATA, api_client=API_CLIENT)
BW_INSTANCES_UTILS = InstancesUtils(api_client=API_CLIENT)

CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")

# Shared thread pool executor for configuration tasks in routes
# This prevents spawning new threads for each config operation. Its tasks flash in the language of
# the request that queued them (see LocaleThreadPoolExecutor).
CONFIG_TASKS_EXECUTOR = LocaleThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-route-tasks")

# Dedicated pool for read-heavy page fan-outs (e.g. /home runs its Redis
# aggregations and DB queries concurrently). Kept separate from
# CONFIG_TASKS_EXECUTOR so a long-running config mutation (import, plugin
# update) can never starve a user-facing page load via head-of-line blocking.
PAGE_TASKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-page-tasks")


LOGGER = getLogger("UI")

PLUGIN_VALIDATOR = None


def invalid_plugin_json(plugin_path: Path, known_plugins: list) -> bool:
    """Whether ``plugin_path`` holds a hand-mounted manifest the scheduler would refuse.

    Such a directory is the operator's only copy: the scheduler keeps it and the database has no row to
    restore it from, so the reload must neither overwrite it nor sweep it away.
    """
    global PLUGIN_VALIDATOR

    if plugin_path.is_symlink() or not plugin_path.joinpath("plugin.json").is_file():
        return False

    try:
        if PLUGIN_VALIDATOR is None:
            gen_path = CORE_PLUGINS_PATH.parent.joinpath("gen").as_posix()
            if gen_path not in sys_path:
                sys_path.append(gen_path)
            from Configurator import Configurator  # type: ignore

            PLUGIN_VALIDATOR = Configurator(CORE_PLUGINS_PATH.parent / "settings.json", CORE_PLUGINS_PATH, [], [], {}, LOGGER)
    except Exception as e:  # without a validator nothing can be called valid, so nothing is replaced or removed
        LOGGER.error(f"Keeping manual plugin {plugin_path.name}: its manifest cannot be validated ({e})")
        return True

    _, problem = read_manual_plugin(plugin_path, PLUGIN_VALIDATOR, known_plugins)
    if problem:
        LOGGER.error(f"Keeping invalid manual plugin {plugin_path.name}: {problem}")
    return bool(problem)


def _rearm_plugin_reload(error: str) -> str:
    """Raise the ``ui_plugins`` flag again so the next request retries, and hand ``error`` back to the caller."""
    try:
        API_CLIENT.checked_changes(["ui_plugins"], value=True)
    except Exception as e:
        LOGGER.error(f"Couldn't raise the reload_ui_plugins flag again: {e}")
    return error


def reload_plugins() -> str:
    """Extract the stored plugins; return "" on success, else the error (the flag is then raised again and the caller must not restart the workers)."""
    # Clear the flag before reading the plugins: an update committed while we extract raises it again instead of being erased.
    error = ""
    try:
        API_CLIENT.checked_changes(["ui_plugins"], value=False)
    except Exception as e:
        LOGGER.error(f"An error occurred when setting the changes to checked: {e}")
        error = f"couldn't clear the reload_ui_plugins flag: {e}"

    try:
        plugins = API_CLIENT.get_plugins(type="all", with_data=True)
    except Exception as e:
        LOGGER.error(f"Couldn't read the plugins to extract: {e}")
        return _rearm_plugin_reload(f"couldn't read the plugins: {e}")

    # No "incomplete data" guard as in dev: 1.7 stores every archive whole, a row never has a checksum and an empty `data`.
    failed = []
    # Collect plugin ids from the database for cleanup later.
    known_plugin_ids = {plugin["id"] for plugin in plugins}

    ignored_plugins = set()
    for plugin in plugins:
        # Determine the correct extraction path based on the plugin type.
        if plugin["type"] in ("external", "ui"):
            plugin_path = EXTERNAL_PLUGINS_PATH
        elif plugin["type"] == "pro":
            plugin_path = PRO_PLUGINS_PATH
        else:
            continue

        target = plugin_path / plugin["id"]
        if plugin["method"] == "manual" and target.is_dir() and invalid_plugin_json(target, plugins):
            continue

        # If the target exists, compare its checksum.
        if target.exists():
            with suppress(StopIteration, IndexError, FileNotFoundError):
                plugin_content = create_plugin_tar_gz(target, arc_root=target.name)
                if bytes_hash(plugin_content, algorithm="sha256") == plugin["checksum"]:
                    ignored_plugins.add(target.name)
                    continue
                LOGGER.debug(f"Checksum of {target} has changed, removing it ...")

            if target.is_symlink() or target.is_file():
                with suppress(OSError):
                    target.unlink()
            elif target.is_dir():
                rmtree(target, ignore_errors=True)

        try:
            if plugin["data"]:
                with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                    # The archive root is the directory name, which need not be the plugin id.
                    roots = {
                        Path(name).parts[0] for name in tar.getnames() if Path(name).parts and not Path(name).is_absolute() and ".." not in Path(name).parts
                    }
                    if plugin["method"] == "manual" and any(
                        (plugin_path / root).is_dir() and invalid_plugin_json(plugin_path / root, plugins) for root in roots
                    ):
                        continue
                    safe_tar_extractall(tar, plugin_path)
                    known_plugin_ids.update(roots)

                plugin_folder = plugin_path / plugin["id"]
                # Add u+x permissions to executable files
                desired_perms = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
                for subdir, pattern in (
                    ("jobs", "*"),
                    ("bwcli", "*"),
                    ("ui", "*.py"),
                ):
                    for executable_file in plugin_folder.joinpath(subdir).rglob(pattern):
                        if executable_file.stat().st_mode & 0o777 != desired_perms:
                            executable_file.chmod(desired_perms)
        except OSError as e:
            LOGGER.debug(format_exc())
            if plugin["method"] != "manual":
                LOGGER.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")
                failed.append(plugin["name"])
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")
            failed.append(plugin["name"])

    # Cleanup: Remove plugin folders that exist on the filesystem but are not in the database.
    for plugin_path in (EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH):
        if plugin_path.exists():
            for item in plugin_path.iterdir():
                if item.name not in known_plugin_ids:
                    if item.is_dir() and invalid_plugin_json(item, plugins):
                        continue
                    LOGGER.debug(f"Plugin {item.name} not found in database, removing it...")
                    with suppress(OSError):
                        if item.is_symlink() or item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            rmtree(item, ignore_errors=True)

    if failed:
        error = f"couldn't extract {', '.join(failed)}"
    return _rearm_plugin_reload(error) if error else ""


def safe_reload_plugins(force: bool = False) -> Optional[str]:
    """Return None when another worker already holds the latch (nothing was done), else the result of ``reload_plugins``."""
    DATA.load_from_file()
    if force or DATA.get("FORCE_RELOAD_PLUGIN", False) or not DATA.get("IS_RELOADING_PLUGINS", False):
        DATA["IS_RELOADING_PLUGINS"] = True
        # The latch only keeps workers from extracting concurrently. It used to be cleared on worker
        # import alone, so once a UI had reloaded, the next plugin change (a delete after an update)
        # was consumed without re-extracting. Re-read first: the file is shared by every worker.
        try:
            return reload_plugins()
        finally:
            DATA.load_from_file()
            DATA["IS_RELOADING_PLUGINS"] = False
