from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from logging import getLogger
from os import sep
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from tarfile import open as tar_open
from traceback import format_exc
import json

from common_utils import bytes_hash  # type: ignore

from app.models.config import Config
from app.models.instance import InstancesUtils
from app.models.ui_data import UIData
from app.models.ui_database import UIDatabase

DB = UIDatabase(getLogger("UI"), log=False)
DATA = UIData(Path(sep, "var", "tmp", "bunkerweb").joinpath("ui_data.json"))

BW_CONFIG = Config(DB, data=DATA)
BW_INSTANCES_UTILS = InstancesUtils(DB)

CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")

# Shared thread pool executor for configuration tasks in routes
# This prevents spawning new threads for each config operation
CONFIG_TASKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-route-tasks")


def reload_plugins():
    plugins = DB.get_plugins(_type="all", with_data=True)
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

        # For manually managed external plugins, the on-disk folder is the source of truth.
        # Do not delete or overwrite them from the UI side – they are synchronized to the
        # database by the scheduler's check_plugin_changes() logic instead.
        if plugin["type"] == "external" and plugin.get("method") == "manual":
            if target.exists():
                DB.logger.debug(f"Skipping reload of manually managed external plugin directory {target} (method=manual)")
            ignored_plugins.add(plugin["id"])
            continue

        # If the target exists, compare its checksum.
        if target.exists():
            with suppress(StopIteration, IndexError, FileNotFoundError):
                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                        tar.add(target, arcname=target.name, recursive=True)
                    plugin_content.seek(0, 0)
                    if bytes_hash(plugin_content, algorithm="sha256") == plugin["checksum"]:
                        ignored_plugins.add(target.name)
                        continue
                    DB.logger.debug(f"Checksum of {target} has changed, removing it ...")

            if target.is_symlink() or target.is_file():
                with suppress(OSError):
                    target.unlink()
            elif target.is_dir():
                rmtree(target, ignore_errors=True)

        # If this plugin was marked as ignored (same checksum or manually managed), do not re-extract.
        if plugin["id"] in ignored_plugins:
            continue

        try:
            if plugin["data"]:
                with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                    try:
                        tar.extractall(plugin_path, filter="fully_trusted")
                    except TypeError:
                        tar.extractall(plugin_path)

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
            DB.logger.debug(format_exc())
            if plugin["method"] != "manual":
                DB.logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")
        except BaseException as e:
            DB.logger.debug(format_exc())
            DB.logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")

    ret = DB.checked_changes(["ui_plugins"])
    if ret:
        DB.logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")

    # Cleanup: Remove plugin folders that exist on the filesystem but are not in the database.
    # For manually managed external plugins (method=manual in plugin.json), keep the on-disk
    # folder even if the database does not yet know about the plugin. The scheduler will
    # reconcile those via check_plugin_changes().
    for plugin_path in (EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH):
        if not plugin_path.exists():
            continue

        for item in plugin_path.iterdir():
            # Skip known plugins that are present in the database.
            if item.name in known_plugin_ids:
                continue

            # For external plugins, preserve manually managed ones based on plugin.json metadata.
            if plugin_path == EXTERNAL_PLUGINS_PATH and item.is_dir():
                plugin_json = item / "plugin.json"
                if plugin_json.exists():
                    try:
                        with plugin_json.open("r", encoding="utf-8") as f:
                            plugin_meta = json.load(f)
                        if plugin_meta.get("method") == "manual":
                            DB.logger.debug(f"Preserving manually managed external plugin directory {item} (method=manual, not yet in database)")
                            continue
                    except Exception:  # noqa: BLE001
                        DB.logger.debug(f"Failed to inspect {plugin_json} while cleaning up plugins:\n{format_exc()}")

            DB.logger.debug(f"Plugin {item.name} not found in database, removing it...")
            with suppress(OSError):
                if item.is_symlink() or item.is_file():
                    item.unlink()
                elif item.is_dir():
                    rmtree(item, ignore_errors=True)


def safe_reload_plugins(force: bool = False):
    DATA.load_from_file()
    if force or DATA.get("FORCE_RELOAD_PLUGIN", False) or not DATA.get("IS_RELOADING_PLUGINS", False):
        DATA["IS_RELOADING_PLUGINS"] = True
        reload_plugins()
